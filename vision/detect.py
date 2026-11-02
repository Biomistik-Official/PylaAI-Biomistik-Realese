import os
import json
import platform
import warnings

import cv2
import numpy as np
import onnxruntime as ort

from common.utils import load_toml_as_dict
from vision.entity_model import EntityBox, decode_pose, read_layout

_TERRAIN_TILE_CLASSES = ['wall', 'bush', 'rope_fence', 'water', 'out_of_bounds']
_SEMANTIC_TILE_NAMES = dict(wall='wall', indestructible_wall='wall', fragile='wall',
                          bush='bush', rope_fence='rope_fence', water='water', out_of_bounds='out_of_bounds')

warnings.filterwarnings(
    "ignore",
    message=".*'pin_memory' argument is set as true but no accelerator is found.*",
    category=UserWarning,
)

debug = load_toml_as_dict("cfg/general_config.toml")["super_debug"] == "yes"


def get_optimal_threads(max_limit=4):
    general_config = load_toml_as_dict("cfg/general_config.toml")
    configured_threads = general_config.get("used_threads", general_config.get("onnx_cpu_threads", "auto"))
    if str(configured_threads).strip().lower() != "auto":
        try:
            threads_amount = max(1, int(configured_threads))
            print(f"Using configured ONNX CPU threads: {threads_amount}.")
            return threads_amount
        except (TypeError, ValueError):
            print(f"Ignoring invalid used_threads={configured_threads!r}; falling back to auto.")

    threads = os.cpu_count() or 2
    threads_amount = min(max(2, threads // 2), max_limit)
    print(f"Detected {threads} CPU threads, using {threads_amount} threads.")
    return threads_amount


_provider_message_printed = False


def _directml_provider():
    device_id = load_toml_as_dict("cfg/general_config.toml").get("directml_device_id", "auto")
    if str(device_id).strip().lower() in ("", "auto", "none"):
        return "DmlExecutionProvider"
    try:
        return ("DmlExecutionProvider", {"device_id": int(device_id)})
    except (TypeError, ValueError):
        print(f"Ignoring invalid directml_device_id={device_id!r}; using default DirectML adapter.")
        return "DmlExecutionProvider"


def _build_providers(preferred_device):
    global _provider_message_printed
    preferred_device = str(preferred_device or "auto").strip().lower()
    available_providers = set(ort.get_available_providers())
    providers = []

    if preferred_device in ("gpu", "auto", "cuda"):
        if "CUDAExecutionProvider" in available_providers:
            providers.append((
                "CUDAExecutionProvider",
                {
                    "cudnn_conv_algo_search": "DEFAULT",
                },
            ))

    if preferred_device in ("gpu", "auto", "directml", "dml"):
        if "DmlExecutionProvider" in available_providers and not providers:
            providers.append(_directml_provider())

    if preferred_device in ("gpu", "auto", "openvino"):
        if "OpenVINOExecutionProvider" in available_providers and not providers:
            providers.append("OpenVINOExecutionProvider")

    if preferred_device in ("gpu", "auto"):
        if "AzureExecutionProvider" in available_providers and not providers:
            providers.append("AzureExecutionProvider")

    providers.append("CPUExecutionProvider")
    if not _provider_message_printed:
        selected = providers[0][0] if isinstance(providers[0], tuple) else providers[0]
        if selected == "CPUExecutionProvider":
            print(
                f"Using CPU inference. Available ONNX providers: {', '.join(ort.get_available_providers())}. "
                f"Python={platform.python_version()} {platform.architecture()[0]}."
            )
        else:
            print(
                f"Using {selected} for ONNX inference with CPU fallback. "
                f"Available ONNX providers: {', '.join(ort.get_available_providers())}. "
                f"Python={platform.python_version()} {platform.architecture()[0]}."
            )
        _provider_message_printed = True
    return providers


def _provider_name(provider):
    return provider[0] if isinstance(provider, tuple) else provider


def _configure_session_options_for_provider(session_options, provider_name):
    if provider_name == "DmlExecutionProvider":
        # ONNX Runtime documents these as required for DirectML sessions.
        # Without them some Windows/NVIDIA/AMD setups can initialize but run
        # extremely slowly or fall back unpredictably.
        session_options.enable_mem_pattern = False
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL


def _numpy_nms(boxes, scores, iou_threshold=0.6):
    if len(boxes) == 0:
        return np.array([], dtype=np.int32)

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[np.where(iou <= iou_threshold)[0] + 1]

    return np.array(keep, dtype=np.int32)


def _postprocess_raw(raw_output, conf_thresh=0.6, iou_thresh=0.6, end2end=False):
    prediction = np.asarray(raw_output[0] if isinstance(raw_output, (list, tuple)) else raw_output)
    if end2end:
        if prediction.ndim == 3:
            prediction = prediction[0]
        if prediction.ndim != 2 or prediction.shape[1] != 6:
            raise ValueError(f'Unexpected end-to-end output: {prediction.shape}')
        return [prediction[(prediction[:, 4] >= conf_thresh) & np.isfinite(prediction).all(1)].copy()]

    if prediction.ndim == 3:
        prediction = prediction[0]
        if prediction.shape[0] < prediction.shape[1]:
            prediction = prediction.T

    if prediction.shape[1] <= 6:
        boxes_xyxy = prediction[:, :4]
        confidences = prediction[:, 4]
        class_ids = prediction[:, 5].astype(np.int32)
    else:
        boxes_cxcywh = prediction[:, :4]
        class_scores = prediction[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = class_scores[np.arange(prediction.shape[0]), class_ids]

        x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
        y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
        x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
        y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

    mask = confidences >= conf_thresh
    if not np.any(mask):
        return []

    boxes_xyxy = boxes_xyxy[mask]
    confidences = confidences[mask]
    class_ids = class_ids[mask]

    results = []
    for class_id in np.unique(class_ids):
        class_mask = class_ids == class_id
        class_boxes = boxes_xyxy[class_mask]
        class_scores = confidences[class_mask]
        keep = _numpy_nms(class_boxes, class_scores, iou_thresh)
        if len(keep) == 0:
            continue

        kept_boxes = class_boxes[keep]
        kept_scores = class_scores[keep]
        kept_classes = np.full((len(keep), 1), class_id, dtype=np.float32)
        results.append(np.hstack([kept_boxes, kept_scores.reshape(-1, 1), kept_classes]))

    return results


class Detect:
    def __init__(self, model_path, ignore_classes=None, classes=None, input_size=(640, 640)):
        self.preferred_device = load_toml_as_dict("cfg/general_config.toml")["cpu_or_gpu"]
        self.model_path = model_path
        self.classes = classes
        self.ignore_classes = set(ignore_classes) if ignore_classes else set()
        self.input_size = input_size

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.model, self.device = self.load_model()
        self.input_name = self.model.get_inputs()[0].name
        self.output_names = [output.name for output in self.model.get_outputs()]
        layout = read_layout(self.model)
        self.keypoint_shape = layout['keypoints']
        self.end_to_end = self.end2end = layout['end_to_end']
        self.classes = layout['classes'] or self.classes
        self.input_size = layout['input_size'] or self.input_size
        self.tile_size = 54
        self.semantic_outputs = {name: i for i, name in enumerate(self.output_names)}
        self.semantic = {'class_ids', 'confidence'}.issubset(self.semantic_outputs)
        if self.semantic:
            with open(os.path.splitext(model_path)[0] + '.json', encoding='utf-8') as handle:
                manifest = json.load(handle)
            self.semantic_names = [manifest['class_ids'][str(i)] for i in range(len(manifest['class_ids']))]
            self.input_size = (manifest['height'], manifest['width'])
            if list(self.model.get_inputs()[0].shape) != [1, 3, *self.input_size]:
                raise ValueError('Terrain model and JSON manifest input sizes do not match.')
            self.classes = list(_TERRAIN_TILE_CLASSES)
        self._padded_img_buffer = np.full(
            (1, 3, self.input_size[0], self.input_size[1]),
            128.0 / 255.0,
            dtype=np.float32,
        )
        self._last_resized_w = 0
        self._last_resized_h = 0

    def load_model(self):
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")
        providers = _build_providers(self.preferred_device)
        first_provider = _provider_name(providers[0])
        _configure_session_options_for_provider(so, first_provider)
        optimal_threads_amount = get_optimal_threads()
        if first_provider == "CPUExecutionProvider":
            so.intra_op_num_threads = optimal_threads_amount
            so.inter_op_num_threads = max(1, min(2, optimal_threads_amount))
        else:
            so.intra_op_num_threads = 1
            so.inter_op_num_threads = 1
        try:
            model = ort.InferenceSession(self.model_path, sess_options=so, providers=providers)
        except Exception:
            if first_provider == 'CPUExecutionProvider':
                raise
            model = ort.InferenceSession(self.model_path, sess_options=so, providers=['CPUExecutionProvider'])
        return model, model.get_providers()[0]

    def preprocess_image(self, img):
        h, w = img.shape[:2]

        scale = min(self.input_size[0] / h, self.input_size[1] / w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        pad_x = pad_y = 0
        if self.end2end or self.semantic or self.keypoint_shape:
            new_w, new_h = round(w * scale), round(h * scale)
            pad_x = (self.input_size[1] - new_w) // 2
            pad_y = (self.input_size[0] - new_h) // 2
            self._padded_img_buffer.fill(114.0 / 255.0)
        elif new_w != self._last_resized_w or new_h != self._last_resized_h:
            self._padded_img_buffer.fill(128.0 / 255.0)
        self._last_resized_w, self._last_resized_h = new_w, new_h

        resized_img = cv2.resize(
            img,
            (new_w, new_h),
            interpolation=cv2.INTER_LINEAR
        )

        img_float = resized_img.astype(np.float32, copy=True)
        np.multiply(img_float, 1.0 / 255.0, out=img_float)

        self._padded_img_buffer[0, 0, pad_y:pad_y + new_h, pad_x:pad_x + new_w] = img_float[:, :, 0]
        self._padded_img_buffer[0, 1, pad_y:pad_y + new_h, pad_x:pad_x + new_w] = img_float[:, :, 1]
        self._padded_img_buffer[0, 2, pad_y:pad_y + new_h, pad_x:pad_x + new_w] = img_float[:, :, 2]

        return self._padded_img_buffer, new_w, new_h

    def postprocess(self, raw_output, orig_img_shape, resized_shape, conf_tresh=0.6):
        if self.semantic:
            return self._semantic_tile_detections(raw_output, orig_img_shape, resized_shape, conf_tresh)

        if self.keypoint_shape:
            detections = decode_pose(raw_output, len(self.classes), self.keypoint_shape, conf_tresh,
                                     self.end_to_end, _numpy_nms, keep_points=True)
        else:
            detections = _postprocess_raw(
                raw_output,
                conf_thresh=conf_tresh,
                iou_thresh=0.6,
                end2end=self.end2end
            )

        orig_h, orig_w = orig_img_shape
        resized_w, resized_h = resized_shape

        scale_w = orig_w / resized_w
        scale_h = orig_h / resized_h

        results = []

        for det in detections:
            if len(det):
                if self.end2end or self.keypoint_shape:
                    det[:, [0, 2]] -= (self.input_size[1] - resized_w) // 2
                    det[:, [1, 3]] -= (self.input_size[0] - resized_h) // 2
                if self.keypoint_shape:
                    det[:, 6] = (det[:, 6] - (self.input_size[1] - resized_w) // 2) * scale_w
                    det[:, 7] = (det[:, 7] - (self.input_size[0] - resized_h) // 2) * scale_h
                    det[:, 6] = np.clip(det[:, 6], 0, orig_w)
                    det[:, 7] = np.clip(det[:, 7], 0, orig_h)
                det[:, 0] *= scale_w
                det[:, 1] *= scale_h
                det[:, 2] *= scale_w
                det[:, 3] *= scale_h
                if self.end2end or self.keypoint_shape:
                    det[:, [0, 2]] = np.clip(det[:, [0, 2]], 0, orig_w)
                    det[:, [1, 3]] = np.clip(det[:, [1, 3]], 0, orig_h)
                results.append(det)

        return results

    def _semantic_tile_detections(self, raw_output, orig_img_shape, resized_shape, conf_tresh):
        """Convert transient semantic predictions to coarse boxes; gameplay only receives ordinary lists."""
        orig_h, orig_w = orig_img_shape
        new_w, new_h = resized_shape
        pad_x = (self.input_size[1] - new_w) // 2
        pad_y = (self.input_size[0] - new_h) // 2
        crop = (0, slice(pad_y, pad_y + new_h), slice(pad_x, pad_x + new_w))
        ids = raw_output[self.semantic_outputs['class_ids']][crop]
        confidence = raw_output[self.semantic_outputs['confidence']][crop]
        scale_x, scale_y = orig_w / new_w, orig_h / new_h
        step_x = max(1, int(self.tile_size / scale_x))
        step_y = max(1, int(self.tile_size / scale_y))
        rows = []

        for class_id, name in enumerate(self.semantic_names):
            tile_name = _SEMANTIC_TILE_NAMES.get(name)
            if tile_name is None:
                continue
            minimum = 0.0 if name == 'out_of_bounds' else max(
                conf_tresh, {'rope_fence': .65, 'water': .75}.get(name, .60))
            region = np.ascontiguousarray((ids == class_id) & (confidence >= minimum), dtype=np.uint8)
            if not region.any():
                continue
            if name != 'out_of_bounds':
                # Same small/weak-component rejection as the deployed semantic model.
                n, labels, stats, _ = cv2.connectedComponentsWithStats(region, connectivity=8)
                area = stats[:, cv2.CC_STAT_AREA]
                mean = np.bincount(labels.ravel(), weights=confidence.ravel(), minlength=n) / np.maximum(area, 1)
                keep = (area >= .0006 * new_w * new_h) & (mean >= .80)
                keep[0] = False
                region = keep[labels].astype(np.uint8)

            x0, y0, width, height = cv2.boundingRect(region)
            output_id = self.classes.index(tile_name)
            # Each occupied cell produces one bounded rectangle, rather than one box around an entire lake/wall.
            for y in range(y0 // step_y * step_y, y0 + height, step_y):
                for x in range(x0 // step_x * step_x, x0 + width, step_x):
                    cell = region[y:y + step_y, x:x + step_x]
                    bx, by, bw, bh = cv2.boundingRect(cell)
                    if not bw or not bh:
                        continue
                    score = float(confidence[y:y + step_y, x:x + step_x][cell > 0].mean())
                    rows.append([int((x + bx) * scale_x), int((y + by) * scale_y),
                                 min(orig_w, int(np.ceil((x + bx + bw) * scale_x))),
                                 min(orig_h, int(np.ceil((y + by + bh) * scale_y))), score, output_id])

        return [np.asarray(rows, dtype=np.float32).reshape(-1, 6)]


    def detect_objects(self, img, conf_tresh=0.6):
        orig_h, orig_w = img.shape[:2]
        preprocessed_img, resized_w, resized_h = self.preprocess_image(img)
        outputs = self.model.run(self.output_names, {self.input_name: preprocessed_img})
        detections = self.postprocess(outputs, (orig_h, orig_w), (resized_w, resized_h), conf_tresh)

        results = {}
        for detection in detections:
            for row in detection:
                x1, y1, x2, y2 = int(row[0]), int(row[1]), int(row[2]), int(row[3])
                class_id = int(row[5])
                if self.classes is None or not 0 <= class_id < len(self.classes):
                    continue
                class_name = self.classes[class_id]

                if class_id in self.ignore_classes or class_name in self.ignore_classes:
                    continue
                box = [x1, y1, x2, y2]
                if self.keypoint_shape and np.isfinite(row[6:8]).all() and (self.keypoint_shape[1] == 2 or row[8] >= .5):
                    box = EntityBox(box, ground=(float(row[6]), float(row[7])))
                results.setdefault(class_name, []).append(box)

        return results
