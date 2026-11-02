import unittest
import numpy as np
from types import SimpleNamespace
from core.play import Movement

from vision.entity_model import decode_pose
from vision.detect import Detect, _numpy_nms


class ModernVisionTests(unittest.TestCase):
    def test_pose_keypoints_are_not_interpreted_as_class_probabilities(self):
        raw = np.array([[[100,100,40,20,.8,.1,300,900,.99]]], dtype=np.float32)
        result = decode_pose(raw, 2, (1,3), .6, False, _numpy_nms)
        np.testing.assert_allclose(result[0][0], [80,90,120,110,.8,0], rtol=1e-6)

    def test_end_to_end_pose_retains_classes_and_drops_invalid_boxes(self):
        raw = np.array([[[10,20,30,40,.9,1,23,34,.8], [40,20,10,40,.9,1,0,0,0]]], dtype=np.float32)
        result = decode_pose(raw, 2, (1,3), .6, True, _numpy_nms)
        self.assertEqual(len(result[0]), 1)
        self.assertEqual(result[0][0,5], 1)

    def test_invalid_pose_layout_reports_error(self):
        with self.assertRaises(ValueError):
            decode_pose(np.zeros((1,7,5)), 2, (1,3), .6, False, _numpy_nms)

    def make_detector(self):
        detector = object.__new__(Detect)
        detector.semantic = False
        detector.keypoint_shape = (1,3)
        detector.end_to_end = True
        detector.end2end = True
        detector.classes = ['player','enemy']
        detector.input_size = (384,640)
        detector._padded_img_buffer = np.zeros((1,3,384,640), dtype=np.float32)
        detector._last_resized_w = detector._last_resized_h = 0
        return detector

    def test_centered_letterbox_is_removed_before_scaling_to_frame(self):
        detector = self.make_detector()
        raw = np.array([[[100,62,200,112,.9,0,150,110,.9]]], dtype=np.float32)
        result = detector.postprocess(raw, (1080,1920), (640,360))
        np.testing.assert_allclose(result[0][0,:4], [300,150,600,300])

    def test_modern_padding_uses_training_color_and_center(self):
        detector = self.make_detector()
        tensor, width, height = detector.preprocess_image(np.full((1080,1920,3),255,np.uint8))
        self.assertEqual((width,height), (640,360))
        self.assertAlmostEqual(float(tensor[0,0,0,0]),114/255,places=6)
        self.assertEqual(float(tensor[0,0,12,0]),1.)

    def test_semantic_wall_and_water_stay_separate(self):
        detector = self.make_detector()
        detector.semantic = True
        detector.input_size = (100,100)
        detector.semantic_outputs = {'class_ids':0,'confidence':1}
        detector.semantic_names = ['ground','wall','water']
        detector.classes = ['wall','bush','rope_fence','water','out_of_bounds']
        detector.tile_size = 20
        ids = np.zeros((1,100,100),np.uint8)
        ids[0,20:40,20:40] = 1
        ids[0,60:80,60:80] = 2
        output = detector.postprocess([ids,np.full((1,100,100),.95,np.float32)], (100,100), (100,100))
        self.assertEqual({int(row[5]) for batch in output for row in batch}, {0,3})

    def test_ground_point_survives_scaling_without_changing_four_coordinate_boxes(self):
        detector=self.make_detector()
        raw=np.array([[[100,62,200,112,.9,0,150,108,.9]]],dtype=np.float32)
        detector.model=SimpleNamespace(run=lambda outputs,feed:raw)
        detector.input_name='images'
        detector.output_names=['output0']
        detector.ignore_classes=set()
        box=detector.detect_objects(np.zeros((1080,1920,3),np.uint8))['player'][0]
        self.assertEqual(len(box),4)
        self.assertEqual(Movement.get_player_pos(box),(450.,288.))
        self.assertEqual(Movement.get_enemy_pos([10,20,30,40]),(20.,30.))
