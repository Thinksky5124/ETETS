'''
Author       : Thyssen Wen
Date         : 2022-10-27 19:28:35
LastEditors  : Thyssen Wen
LastEditTime : 2022-10-28 09:45:56
Description  : Optical Flow Post Processing
FilePath     : /SVTAS/svtas/model/post_precessings/optical_flow_post_processing.py
'''
import numpy as np
import torch
from ...utils.flow_vis import make_colorwheel
from ..builder import POSTPRECESSING
from ...loader.transform.transform import VideoStreamTransform

@POSTPRECESSING.register()
class OpticalFlowPostProcessing():
    def __init__(self,
                 sliding_window,
                 post_transforms=[dict(Clamp = dict(min_val=-20, max_val=20)),
                                            dict(ToUInt8 = None)],
                 fps=15,
                 need_visualize=False,
                 ignore_index=-100):
        self.sliding_window = sliding_window
        self.fps = fps
        self.need_visualize = need_visualize
        self.post_transforms = VideoStreamTransform(post_transforms)
        self.init_flag = False
        self.colorwheel = make_colorwheel()  # shape [55x3]
        self.ignore_index = ignore_index
    
    def init_scores(self, sliding_num, batch_size):
        self.flow_img_list = []
        self.flow_visual_list = []
        self.video_gt = []
        self.init_flag = True

    def update(self, flow_imgs, gt, idx):
        # seg_scores [stage_num N C T]
        # gt [N T]
        for bs in range(flow_imgs.shape[0]):
            results = {}
            results['imgs'] = flow_imgs[bs, :]
            flows = self.post_transforms(results)['imgs']
            flows = flows.cpu().permute(0, 2, 3, 1).numpy()
            self.flow_img_list.append(np.expand_dims(flows, 0))
            self.video_gt.append(gt[:, 0:self.sliding_window].detach().cpu().numpy().copy())

            if self.need_visualize:
                u = flows[:, :, :, 0]
                v = flows[:, :, :, 1]
                rad = np.sqrt(np.square(u) + np.square(v))
                rad_max = np.max(rad)
                epsilon = 1e-5
                u = u / (rad_max + epsilon)
                v = v / (rad_max + epsilon)
                
                flows_image = np.zeros((u.shape[0], u.shape[1], u.shape[2], 3), np.uint8)

                ncols = self.colorwheel.shape[0]
                rad = np.sqrt(np.square(u) + np.square(v))
                a = np.arctan2(-v, -u)/np.pi
                fk = (a + 1) / 2 * (ncols - 1)
                k0 = np.floor(fk).astype(np.int32)
                k1 = k0 + 1
                k1[k1 == ncols] = 0
                f = fk - k0
                for i in range(self.colorwheel.shape[1]):
                    tmp = self.colorwheel[:, i]
                    col0 = tmp[k0] / 255.0
                    col1 = tmp[k1] / 255.0
                    col = (1 - f) * col0 + f * col1
                    idx = (rad <= 1)
                    col[idx]  = 1 - rad[idx] * (1-col[idx])
                    col[~idx] = col[~idx] * 0.75   # out of range
                    # Note the 2-i => BGR instead of RGB
                    ch_idx = 2 - i
                    flows_image[:, :, :, ch_idx] = np.floor(255 * col)
                self.flow_visual_list.append(np.expand_dims(flows_image, 0))


    def output(self):
        # save flow imgs
        flow_imgs_list = []
        flow_imgs = np.concatenate(self.flow_img_list, axis=1)
        flow_imgs = np.concatenate([np.zeros_like(flow_imgs[:, 0:1, :]), flow_imgs], axis=1)
        video_gt = np.concatenate(self.video_gt, axis=1)
        if self.need_visualize:
            flow_visual_imgs_list = []
            flow_visual_imgs = np.concatenate(self.flow_visual_list, axis=1)
            flow_visual_imgs = np.concatenate([np.zeros_like(flow_visual_imgs[:, 0:1, :]), flow_visual_imgs], axis=1)

        for bs in range(flow_imgs.shape[0]):
            index = np.where(video_gt[bs, :] == self.ignore_index)
            ignore_start = min(list(index[0]) + [video_gt.shape[-1]])
            imgs = flow_imgs[bs, :ignore_start]
            flow_imgs_list.append(imgs.copy())

            if self.need_visualize:
                visual_imgs = flow_visual_imgs[bs, :ignore_start]
                flow_visual_imgs_list.append(visual_imgs.copy())
            
        if self.need_visualize:
            return flow_imgs_list, flow_visual_imgs_list, self.fps
        else:
            return flow_imgs_list
