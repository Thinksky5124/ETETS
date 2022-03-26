'''
Author: Thyssen Wen
Date: 2022-03-18 19:25:14
LastEditors: Thyssen Wen
LastEditTime: 2022-03-26 15:03:12
Description: data prepare pipline function
FilePath: /ETESVS/dataset/pipline.py
'''
import torchvision.transforms as transforms
import decord as de
import numpy as np
import torch
import copy
from PIL import Image

class BatchCompose(object):
    def __init__(self, to_tensor_idx=3):
        self.to_tensor_idx = to_tensor_idx

    def __call__(self, batch):
        result_batch = []
        for index in range(len(batch)):
            data = []
            for i in range(len(batch[index])):
                if i < self.to_tensor_idx:
                    if not torch.is_tensor(batch[index][i]):
                        data.append(torch.tensor(batch[index][i]))
                    else:
                        data.append(batch[index][i])
                else:
                    data.append(batch[index][i])
            result_batch.append(data)
        return result_batch

class Pipeline(object):
    def __init__(self,
                 decode=None,
                 sample=None,
                 transform=None):
        self.decode = VideoDecoder(**decode)
        self.sample = VideoStreamSampler(**sample)
        self.transform = VideoStreamTransform(transform)

    def __call__(self, results):
        # decode
        results = self.decode(results)
        # sample
        results = self.sample(results)
        # transform
        results = self.transform(results)
        return results

class VideoDecoder(object):
    """
    Decode mp4 file to frames.
    Args:
        filepath: the file path of mp4 file
    """
    def __init__(self,
                 backend='decord'):

        self.backend = backend

    def __call__(self, results):
        """
        Perform mp4 decode operations.
        return:
            List where each item is a numpy array after decoder.
        """
        file_path = results['filename']
        results['format'] = 'video'
        results['backend'] = self.backend

        container = de.VideoReader(file_path)
        video_len = len(container)
        results['frames'] = container
        results['frames_len'] = results['raw_labels'].shape[0]
        results['video_len'] = video_len
        
        return results

class VideoStreamSampler(object):
    """
    Sample frames id.
    Returns:
        frames_idx: the index of sampled #frames.
    """

    def __init__(self,
                 seg_len,
                 sample_rate=4,
                 clip_seg_num=15,
                 sliding_window=60,
                 ignore_index=-100,
                 ):
        self.sample_rate = sample_rate
        self.seg_len = seg_len
        self.clip_seg_num = clip_seg_num
        self.sliding_window = sliding_window
        self.ignore_index = ignore_index

    def __call__(self, results):
        """
        Args:
            frames_len: length of frames.
        return:
            sampling id.
        """
        frames_len = int(results['frames_len'])
        video_len = int(results['video_len'])
        results['frames_len'] = frames_len
        container = results['frames']
        imgs = []
        labels = results['raw_labels']

        # generate sample index
        start_frame = results['sample_sliding_idx'] * self.sliding_window
        end_frame = start_frame + self.clip_seg_num * self.sample_rate
        if start_frame < frames_len and end_frame < frames_len:
            vid_end_frame = end_frame
            if end_frame > video_len:
                vid_end_frame = video_len
            frames_idx = list(range(start_frame, vid_end_frame, self.sample_rate))
            labels = labels[start_frame:end_frame]
            frames_select = container.get_batch(frames_idx)
            # dearray_to_img
            np_frames = frames_select.asnumpy()
            for i in range(np_frames.shape[0]):
                imgbuf = np_frames[i]
                imgs.append(Image.fromarray(imgbuf, mode='RGB'))

            if len(imgs) < self.clip_seg_num:
                np_frames = np_frames[-1].asnumpy()
                pad_len = self.clip_seg_num - len(imgs)
                for i in range(pad_len):
                    imgs.append(Image.fromarray(np_frames, mode='RGB'))
                    
            mask = np.ones((labels.shape[0]))
        elif start_frame < frames_len and end_frame >= frames_len:
            frames_idx = list(range(start_frame, video_len, self.sample_rate))
            labels = labels[start_frame:frames_len]
            frames_select = container.get_batch(frames_idx)
            # dearray_to_img
            np_frames = frames_select.asnumpy()
            for i in range(np_frames.shape[0]):
                imgbuf = np_frames[i]
                imgs.append(Image.fromarray(imgbuf, mode='RGB'))
            np_frames = np.zeros_like(np_frames[0])
            pad_len = self.clip_seg_num - len(imgs)
            for i in range(pad_len):
                imgs.append(Image.fromarray(np_frames, mode='RGB'))
            vaild_mask = np.ones((labels.shape[0]))
            mask_pad_len = self.clip_seg_num * self.sample_rate - labels.shape[0]
            void_mask = np.zeros((mask_pad_len))
            mask = np.concatenate([vaild_mask, void_mask], axis=0)
            labels = np.concatenate([labels, np.full((mask_pad_len), self.ignore_index)])
        else:
            np_frames = np.zeros((240, 320, 3))
            pad_len = self.clip_seg_num
            for i in range(pad_len):
                imgs.append(Image.fromarray(np_frames, mode='RGB'))
            mask = np.zeros((self.clip_seg_num * self.sample_rate))
            labels = np.full((self.clip_seg_num * self.sample_rate), self.ignore_index)

        results['imgs'] = imgs[:self.clip_seg_num]
        results['labels'] = labels.copy()
        results['mask'] = mask.copy()
        return results

class VideoStreamTransform(object):
    def __init__(self, transform_list):
        transform_op_list = []
        for transforms_op in transform_list:
            name = list(transforms_op.keys())[0]
            if list(transforms_op.values())[0] is None:
                op = getattr(transforms, name)()
            else:
                op = getattr(transforms, name)(**list(transforms_op.values())[0])
            transform_op_list.append(op)
        self.imgs_transforms_pipeline = transforms.Compose(transform_op_list)

    def __call__(self, results):
        imgs = []
        for img in results['imgs']:
            img = self.imgs_transforms_pipeline(img)
            imgs.append(img.unsqueeze(0))
        imgs = torch.cat(imgs, dim=0)
        results['imgs'] = copy.deepcopy(imgs)
        return results