'''
Author       : Thyssen Wen
Date         : 2022-05-18 14:55:53
LastEditors  : Thyssen Wen
LastEditTime : 2022-11-11 14:11:43
Description  : datatset class
FilePath     : /SVTAS/svtas/loader/dataset/__init__.py
'''
from .item_base_dataset import (FeatureSegmentationDataset,
                                RawFrameSegmentationDataset)
from .stream_base_dataset import (FeatureStreamSegmentationDataset,
                                  FeatureVideoPredictionDataset,
                                  RawFrameStreamCAMDataset,
                                  RawFrameStreamSegmentationDataset,
                                  RGBFlowFrameStreamSegmentationDataset,
                                  CompressedVideoStreamSegmentationDataset,
                                  RGBMVsResFrameStreamSegmentationDataset)

__all__ = [
    'RawFrameStreamSegmentationDataset', 'FeatureStreamSegmentationDataset',
    'RGBFlowFrameStreamSegmentationDataset',
    'FeatureVideoPredictionDataset', 'FeatureSegmentationDataset',
    'RawFrameSegmentationDataset', 'RawFrameStreamCAMDataset',
    'CompressedVideoStreamSegmentationDataset',
    'RGBMVsResFrameStreamSegmentationDataset'
]