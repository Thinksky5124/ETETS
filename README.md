# SVTAS
Streaming Video Temporal Action Segmentation In Real Time
- [paper](https://arxiv.org/pdf/2209.13808.pdf)

## Abstract

Temporal action segmentation (TAS) is a critical step toward long-term video understanding. Recent studies follow a pattern that builds models based on features instead of raw video picture information. However, we claim those models are trained complicatedly and limit application scenarios. It is hard for them to segment human actions of video in real time because they must work after the full video features are extracted. As the real-time action segmentation task is different from TAS task, we define it as streaming video real-time temporal action segmentation (SVTAS) task.

# Framework Feature
- [x] Distribution train
- [x] Tensorboard visualization
- [x] Caculate model Params and Flops
- [x] Apex accelerate
- [x] Apex ditributedd accelerate
- [x] Pillow-SMID accelerate sample
- [x] Onnxruntime Infer Suppport
- [x] Support CAM Visualization

# Envirnment Prepare

- Linux Ubuntu 20.04+
- Python 3.8+
- PyTorch 1.11+
- CUDA 11.3+
- Cudnn 8.2+
- Pillow-SIMD (optional): Install it by the following scripts.

```bash
conda uninstall -y --force pillow pil jpeg libtiff libjpeg-turbo
pip   uninstall -y         pillow pil jpeg libtiff libjpeg-turbo
conda install -yc conda-forge libjpeg-turbo
CFLAGS="${CFLAGS} -mavx2" pip install --upgrade --no-cache-dir --force-reinstall --no-binary :all: --compile pillow-simd
conda install -y jpeg libtiff
```

- use pip to install environment

```bash
conda create -n torch python=3.8
python -m pip install --upgrade pip
pip install -r requirements.txt

# export
pip freeze > requirements.txt
```
- If report `correlation_cuda package no found`, you should read [Install](model/backbones/utils/liteflownet_v3/README.md)

# Prepare Data

Read Doc [Prepare Datset](doc/prepare_dataset.md)

# Usage
Read Doc [Usage](doc/usage.md)

# Citation
```bib
@misc{2209.13808,
Author = {Wujun Wen and Yunheng Li and Zhuben Dong and Lin Feng and Wanxiao Yang and Shenlan Liu},
Title = {Streaming Video Temporal Action Segmentation In Real Time},
Year = {2022},
Eprint = {arXiv:2209.13808},
}
```
