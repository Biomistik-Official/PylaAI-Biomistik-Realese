import argparse
import subprocess
import sys


ONNX_VARIANTS = [
    "onnxruntime",
    "onnxruntime-gpu",
    "onnxruntime-directml",
    "onnxruntime-openvino",
]


def run(command):
    print(" ".join(command))
    subprocess.check_call(command)


def install_variant(variant):
    package = {
        "directml": "onnxruntime-directml",
        "cuda": "onnxruntime-gpu",
        "cpu": "onnxruntime",
    }[variant]

    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", *ONNX_VARIANTS], check=False)
    run([sys.executable, "-m", "pip", "install", "--upgrade", package])


def main():
    parser = argparse.ArgumentParser(
        description="Switch Pyla-Biomistik's ONNX runtime between DirectML, CUDA, and CPU."
    )
    parser.add_argument(
        "variant",
        choices=["directml", "cuda", "cpu"],
        help="directml is recommended on Windows for NVIDIA/AMD/Intel. cuda requires a compatible NVIDIA CUDA setup.",
    )
    args = parser.parse_args()

    install_variant(args.variant)

    import onnxruntime as ort

    print()
    print(f"Installed ONNX Runtime: {ort.__version__}")
    print(f"Available providers: {', '.join(ort.get_available_providers())}")
    if args.variant == "directml" and "DmlExecutionProvider" not in ort.get_available_providers():
        print("WARNING: DirectML provider is not visible. Restart the terminal and run setup again.")
    elif args.variant == "cuda" and "CUDAExecutionProvider" not in ort.get_available_providers():
        print("WARNING: CUDA provider is not visible. Use DirectML unless CUDA drivers/runtime are installed correctly.")
    else:
        print("GPU runtime switch completed.")


if __name__ == "__main__":
    main()
