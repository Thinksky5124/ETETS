'''
Author       : Thyssen Wen
Date         : 2022-05-21 11:09:06
LastEditors  : Thyssen Wen
LastEditTime : 2023-10-17 10:24:39
Description  : Transeger framework
FilePath     : /SVTAS/svtas/model/architectures/segmentation/transeger.py
'''
import torch
import torch.nn as nn

from ....utils import AbstractBuildFactory

@AbstractBuildFactory.register('model')
class Transeger(nn.Module):
    def __init__(self,
                 image_backbone=None,
                 text_backbone=None,
                 joint=None,
                 weight_init_cfg=None):
        super().__init__()
        self.image_backbone = AbstractBuildFactory.create_factory('model').create(image_backbone)
        self.text_backbone = AbstractBuildFactory.create_factory('model').create(text_backbone)
        self.joint = AbstractBuildFactory.create_factory('model').create(joint)

        # memory last clip labels
        self.last_clip_labels = None
    
    def init_weights(self, init_cfg: dict = {}):
        self.joint.init_weights()
    
    def _clear_memory_buffer(self):
        if self.image_backbone is not None:
            self.image_backbone._clear_memory_buffer()
        if self.text_backbone is not None:
            self.text_backbone._clear_memory_buffer()
        if self.joint is not None:
            self.joint._clear_memory_buffer()
        self.last_clip_labels = None
    
    def forward(self, input_data):
        if self.training:
            masks = input_data['masks']
            imgs = input_data['imgs']
            labels = input_data['labels']
            if self.last_clip_labels is None:
                self.last_clip_labels = labels.detach().clone()
                last_clip_labels = None
            else:
                last_clip_labels = self.last_clip_labels.detach().clone()
                self.last_clip_labels = labels.detach().clone()
        else:
            masks = input_data['masks']
            imgs = input_data['imgs']
            if self.last_clip_labels is None:
                last_clip_labels = None
            else:
                last_clip_labels = self.last_clip_labels.detach().clone()

        ## image encoder
        if self.image_backbone is not None:
            img_input = {"imgs": imgs, "masks": masks}
            img_output = self.image_backbone(img_input)
            img_feature = img_output
        else:
            img_feature = imgs
        
        ### text encoder
        if self.text_backbone is not None:
            text_input = {"x": last_clip_labels, "masks": masks}
            text_output = self.text_backbone(text_input)
            text_feature = text_output
        else:
            text_feature = labels

        ### joint img and text
        if self.joint is not None:
            joint_score = self.joint(img_feature, text_feature, masks)
        else:
            joint_score = None
        # img_seg_score [stage_num, N, C, T]
        # img_extract_score [N, C, T]
        # joint_score [num_satge N C T]
        if not self.training:
            self.last_clip_labels = torch.argmax(joint_score[-1], dim=-2).detach().clone()
        return {"output":joint_score}