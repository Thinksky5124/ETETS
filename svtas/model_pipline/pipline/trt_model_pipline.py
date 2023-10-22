'''
Author       : Thyssen Wen
Date         : 2023-10-22 16:35:05
LastEditors  : Thyssen Wen
LastEditTime : 2023-10-22 16:36:46
Description  : file content
FilePath     : /SVTAS/svtas/model_pipline/pipline/trt/trt_model_pipline.py
'''
from typing import Any, Dict
from .base_pipline import BaseInferModelPipline
from svtas.utils import AbstractBuildFactory, get_logger
from svtas.utils import is_tensorboard_available
from ..wrapper import TensorRTModel

if is_tensorboard_available():
    import tensorrt as trt

@AbstractBuildFactory.register('model_pipline')
class TensorRTModelPipline(BaseInferModelPipline):
    def __init__(self,
                 model: Dict | TensorRTModel,
                 post_processing:
                 Dict, device=None) -> None:
        super().__init__(model, post_processing, device)
        if isinstance(model, TensorRTModel):
            self.model = model
    
    def load_from_ckpt_file(self, ckpt_path: str = None):
        ckpt_path = self.load_from_ckpt_file_ckeck(ckpt_path)
        trt_logger = trt.Logger(trt.Logger.VERBOSE)
        with open(ckpt_path, "rb") as f:
            trt_engine = trt.Runtime(trt_logger).deserialize_cuda_engine(f)
        self.model = trt_engine