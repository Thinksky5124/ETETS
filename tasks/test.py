def test(cfg, weights):
    pass

import os.path as osp
import time
import numpy as np
import torch
from utils.logger import get_logger, AverageMeter, log_batch
from utils.save_load import mkdir

from model.etets import ETETS
from model.loss import ETETSLoss
from dataset.segmentation_dataset import SegmentationDataset
from dataset.segmentation_dataset import VideoSamplerDataset
from utils.metric import SegmentationMetric
from dataset.pipline import Pipeline
from dataset.pipline import BatchCompose
from model.post_processing import PostProcessing

logger = get_logger("ETETS")

@torch.no_grad()
def test(cfg, weights):
    # 1. Construct model.
    model = ETETS(**cfg.MODEL).cuda()
    criterion = ETETSLoss(**cfg.MODEL.loss)

    # 2. Construct dataset and dataloader.
    batch_size = cfg.DATASET.get("test_batch_size", 8)
    test_Pipeline = Pipeline(**cfg.PIPELINE.test)
    test_video_sampler_dataloader = torch.utils.data.DataLoader(
                VideoSamplerDataset(file_path=cfg.DATASET.test.file_path,
                                    gt_path=cfg.DATASET.test.gt_path,
                                    dataset_type=cfg.DATASET.test.dataset_type),
                                    batch_size=batch_size,
                                    num_workers=1,
                                    shuffle=False)
    sliding_concate_fn = BatchCompose(**cfg.COLLATE)

    # default num worker: 0, which means no subprocess will be created
    num_workers = cfg.DATASET.get('num_workers', 0)

    model.eval()

    state_dicts = torch.load(weights)
    model.set_state_dict(state_dicts)

    # add params to metrics
    Metric = SegmentationMetric(cfg.METRIC)
    
    for vid_list, temporal_len_list in test_video_sampler_dataloader:
        test_dataset_config = cfg.DATASET.test
        test_dataset_config['sample_idx_list'] = list(vid_list.numpy())
        test_dataset_config['pipeline'] = test_Pipeline
        test_loader = torch.utils.data.DataLoader(
            SegmentationDataset(**test_dataset_config),
            batch_size=batch_size,
            num_workers=num_workers,
            collate_fn=sliding_concate_fn,
            shuffle=False
        )

        # prepare video score 
        post_processing = PostProcessing(
            batch_size=batch_size,
            max_temporal_len=np.max(temporal_len_list.numpy()),
            num_classes=cfg.MODEL.head.num_classes,
            clip_seg_num=cfg.MODEL.neck.clip_seg_num,
            sliding_window=cfg.DATASET.test.sliding_window,
            sample_rate=cfg.DATASET.test.sample_rate,
            clip_buffer_num=cfg.MODEL.neck.clip_buffer_num)

        # videos sliding stream train
        videos_loss = 0.
        num_clip = test_loader.__len__()
        for i, data in enumerate(test_loader):
            for sliding_seg in data:
                imgs, labels, masks, _, idx = sliding_seg
                # val segment
                outputs = model(imgs, masks)
                cls_score, seg_score = outputs
                cls_loss, seg_loss = criterion(cls_score, seg_score, masks, labels)

                loss = (cls_loss + seg_loss) / num_clip

                loss.backward()
                post_processing.update(seg_score, labels, idx)
                videos_loss += loss.item()
            
        # get pred result
        pred_score_list, pred_cls_list, ground_truth_list = post_processing.output()
        outputs = dict(predict=pred_cls_list,
                    output_np=pred_score_list)
        f1 = Metric.update(list(vid_list.numpy()), ground_truth_list, outputs)
    Metric.accumulate()