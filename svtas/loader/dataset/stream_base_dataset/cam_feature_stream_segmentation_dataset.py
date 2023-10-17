'''
Author: Thyssen Wen
Date: 2022-04-27 16:13:11
LastEditors  : Thyssen Wen
LastEditTime : 2023-10-16 20:38:22
Description: feature dataset class
FilePath     : /SVTAS/svtas/loader/dataset/stream_base_dataset/cam_feature_stream_segmentation_dataset.py
'''

import copy
import os
import os.path as osp

import numpy as np
import torch

from svtas.utils import AbstractBuildFactory
from .stream_base_dataset import StreamDataset


@AbstractBuildFactory.register('dataset')
class CAMFeatureStreamSegmentationDataset(StreamDataset):
    def __init__(self,
                 feature_path,
                 sliding_window=60,
                 flow_feature_path=None,
                 need_precise_grad_accumulate=True,
                 **kwargs):
        self.flow_feature_path = flow_feature_path
        self.feature_path = feature_path
        self.sliding_window = sliding_window
        self.need_precise_grad_accumulate = need_precise_grad_accumulate
        super().__init__(**kwargs)
    
    def parse_file_paths(self, input_path):
        if self.dataset_type in ['gtea', '50salads', 'breakfast', 'thumos14']:
            file_ptr = open(input_path, 'r')
            info = file_ptr.read().split('\n')[:-1]
            file_ptr.close()
        return info
    
    def load_file(self, sample_videos_list):
        """Load index file to get video feature information."""
        video_segment_lists = self.parse_file_paths(self.file_path)
        info_list = [[] for i in range(self.nprocs)]
        # sample step
        for step, sample_idx_list in sample_videos_list:
            # sample step clip
            video_sample_segment_lists = [[] for i in range(self.nprocs)]
            for sample_idx_list_idx in range(len(sample_idx_list)):
                nproces_idx = sample_idx_list_idx % self.nprocs
                sample_idx = sample_idx_list[sample_idx_list_idx]
                video_sample_segment_lists[nproces_idx].append(video_segment_lists[sample_idx])

            max_len = 0
            info_proc = [[] for i in range(self.nprocs)]
            for proces_idx in range(self.nprocs):
                # convert sample
                info = []
                for video_segment in video_sample_segment_lists[proces_idx]:
                    if self.dataset_type in ['gtea', '50salads', 'breakfast', 'thumos14']:
                        video_name = video_segment.split('.')[0]
                        label_path = os.path.join(self.gt_path, video_name + '.txt')

                        video_path = os.path.join(self.feature_path, video_name + '.npy')
                        if not osp.isfile(video_path):
                            raise NotImplementedError
                    file_ptr = open(label_path, 'r')
                    content = file_ptr.read().split('\n')[:-1]
                    classes = np.zeros(len(content), dtype='int64')
                    for i in range(len(content)):
                        classes[i] = self.actions_dict[content[i]]

                    # caculate sliding num
                    if max_len < len(content):
                        max_len = len(content)
                    if self.need_precise_grad_accumulate:
                        precise_sliding_num = len(content) // self.sliding_window
                        if len(content) % self.sliding_window != 0:
                            precise_sliding_num = precise_sliding_num + 1
                    else:
                        precise_sliding_num = 1

                    if self.flow_feature_path is not None:
                        flow_feature_path = os.path.join(self.flow_feature_path, video_name + '.npy')
                        info.append(
                            dict(filename=video_path,
                                flow_feature_name=flow_feature_path,
                                raw_labels=classes,
                                video_name=video_name,
                                precise_sliding_num=precise_sliding_num))
                    else:
                        info.append(
                            dict(filename=video_path,
                                raw_labels=classes,
                                video_name=video_name,
                                precise_sliding_num=precise_sliding_num))
                        
                info_proc[proces_idx] = info

            # construct sliding num
            sliding_num = max_len // self.sliding_window
            if max_len % self.sliding_window != 0:
                sliding_num = sliding_num + 1

            # nprocs sync
            for proces_idx in range(self.nprocs):
                info_list[proces_idx].append([step, sliding_num, info_proc[proces_idx]])
        return info_list
