'''
Author: Thyssen Wen
Date: 2022-03-21 15:22:51
LastEditors: Thyssen Wen
LastEditTime: 2022-04-25 20:43:55
Description: runner script
FilePath: /ETESVS/tasks/runner.py
'''
import torch
import time
from utils.logger import log_batch
import torch.distributed as dist
try:
    from apex import amp
except:
    pass

def reduce_mean(tensor, nprocs):
    rt = tensor.clone()
    dist.all_reduce(rt, op=dist.ReduceOp.SUM) # sum-up as the all-reduce operation
    rt /= nprocs # NOTE this is necessary, since all_reduce here do not perform average 
    return rt

class Runner():
    def __init__(self,
                 logger,
                 video_batch_size,
                 Metric,
                 cfg,
                 model,
                 post_processing,
                 record_dict=None,
                 criterion=None,
                 optimizer=None,
                 use_amp=False,
                 nprocs=1,
                 local_rank=-1,
                 runner_mode='train'):
        self.optimizer = optimizer
        self.logger = logger
        self.video_batch_size = video_batch_size
        self.Metric = Metric
        self.record_dict = record_dict
        self.cfg = cfg
        self.model = model
        self.criterion = criterion
        self.post_processing = post_processing
        self.nprocs = nprocs
        self.local_rank = local_rank
        self.use_amp = use_amp

        assert runner_mode in ['train', 'validation', 'test'], "Not support this runner mode: " + runner_mode
        self.runner_mode = runner_mode
    
    def epoch_init(self):
        # batch videos sampler
        self.videos_loss = 0.
        self.video_backbone_loss = 0.
        self.video_neck_loss = 0.
        self.video_head_loss = 0.
        self.seg_acc = 0.
        self.post_processing.init_flag = False
        self.current_step = 0
        self.current_step_vid_list = None

        if self.runner_mode in ['train']:
            self.model.train()
            self.b_tic = time.time()
            # reset recoder
            for _, recod in self.record_dict.items():
                recod.reset()

        elif self.runner_mode in ['validation']:
            self.model.eval()
            self.b_tic = time.time()
            # reset recoder
            for _, recod in self.record_dict.items():
                recod.reset()

        elif self.runner_mode in ['test']:
            self.model.eval()
        
        
    def batch_end_step(self, sliding_num, vid_list, step, epoch):
        if self.runner_mode in ['train']:
            self.optimizer.step()
            self.optimizer.zero_grad()

        # clear memory buffer
        if self.nprocs > 1:
            self.model.module._clear_memory_buffer()
        else:
            self.model._clear_memory_buffer()

        # get pred result
        pred_score_list, pred_cls_list, ground_truth_list = self.post_processing.output()
        outputs = dict(predict=pred_cls_list,
                        output_np=pred_score_list)
        vid = self.current_step_vid_list

        if self.runner_mode in ['validation', 'test']:
            # distribution                
            if self.nprocs > 1:
                collect_dict = dict(
                    predict=pred_cls_list,
                    output_np=pred_score_list,
                    ground_truth=ground_truth_list,
                    vid=self.current_step_vid_list
                )
                gather_objects = [collect_dict for _ in range(self.nprocs)] # any picklable object
                output_list = [None for _ in range(self.nprocs)]
                dist.all_gather_object(output_list, gather_objects[dist.get_rank()])
                # collect
                pred_cls_list_i = []
                pred_score_list_i = []
                ground_truth_list_i = []
                vid_i = []
                for output_dict in output_list:
                    pred_cls_list_i = pred_cls_list_i + output_dict["predict"]
                    pred_score_list_i = pred_score_list_i + output_dict["output_np"]
                    ground_truth_list_i = ground_truth_list_i + output_dict["ground_truth"]
                    vid_i = vid_i + output_dict["vid"]
                outputs = dict(predict=pred_cls_list_i,
                                output_np=pred_score_list_i)
                ground_truth_list = ground_truth_list_i
                vid = vid_i

        f1, acc = self.Metric.update(vid, ground_truth_list, outputs)

        self.current_step_vid_list = vid_list
        if len(self.current_step_vid_list) > 0:
            self.post_processing.init_scores(sliding_num, len(vid_list))
        

        if self.runner_mode in ['train', 'validation']:
            if self.nprocs > 1:
                torch.distributed.barrier()
                self.video_backbone_loss = reduce_mean(self.video_backbone_loss, self.nprocs)
                self.video_neck_loss = reduce_mean(self.video_neck_loss, self.nprocs)
                self.video_head_loss = reduce_mean(self.video_head_loss, self.nprocs)

            # logger
            if self.runner_mode in ['train']:
                self.record_dict['lr'].update(self.optimizer.state_dict()['param_groups'][0]['lr'], self.video_batch_size)
            
            self.record_dict['loss'].update(self.videos_loss.item(), self.video_batch_size)
            self.record_dict['batch_time'].update(time.time() - self.b_tic)
            self.record_dict['F1@0.5'].update(f1, self.video_batch_size)
            self.record_dict['Acc'].update(acc, self.video_batch_size)
            self.record_dict['Seg_Acc'].update(self.seg_acc, self.video_batch_size)
            self.record_dict['backbone_loss'].update(self.video_backbone_loss.item(), self.video_batch_size)
            self.record_dict['neck_loss'].update(self.video_neck_loss.item(), self.video_batch_size)
            self.record_dict['head_loss'].update(self.video_head_loss.item(), self.video_batch_size)

            self.videos_loss = 0.
            self.video_backbone_loss = 0.
            self.video_neck_loss = 0.
            self.video_head_loss = 0.
            self.seg_acc = 0.

            if self.current_step % self.cfg.get("log_interval", 10) == 0:
                ips = "ips: {:.5f} instance/sec.".format(
                    self.video_batch_size / self.record_dict["batch_time"].val)
                if self.runner_mode in ['train']:
                    log_batch(self.record_dict, self.current_step, epoch + 1, self.cfg.epochs, "train", ips, self.logger)
                elif self.runner_mode in ['validation']:
                    log_batch(self.record_dict, self.current_step, epoch + 1, self.cfg.epochs, "validation", ips, self.logger)

            self.b_tic = time.time()

        self.current_step = step

    def run_one_clip(self, imgs, labels, masks, vid_list, sliding_num, idx):
        # move data
        imgs = imgs.cuda()
        masks = masks.cuda()
        labels = labels.cuda()
        # train segment
        if self.nprocs > 1 and idx < sliding_num - 1 and self.use_amp is False:
            with self.model.no_sync():
                # multi-gpus
                outputs = self.model(imgs, masks, idx)
                backbone_score, neck_score, head_score = outputs
                if self.runner_mode in ['train', 'validation']:
                    backone_loss, neck_loss, head_loss = self.criterion(backbone_score, neck_score, head_score, masks, labels)
                
                    loss = (backone_loss + neck_loss + head_loss) / sliding_num

                    if self.runner_mode in ['train']:
                        if self.use_amp is True:
                            with amp.scale_loss(loss, self.optimizer) as scaled_loss:
                                scaled_loss.backward()
                        else:
                            loss.backward()
        else:
            # single gpu
            outputs = self.model(imgs, masks, idx)
            backbone_score, neck_score, head_score= outputs
            if self.runner_mode in ['train', 'validation']:
                backone_loss, neck_loss, head_loss = self.criterion(backbone_score, neck_score, head_score, masks, labels)
            
                loss = (backone_loss + neck_loss + head_loss) / sliding_num

                if self.runner_mode in ['train']:
                    if self.use_amp is True:
                        with amp.scale_loss(loss, self.optimizer) as scaled_loss:
                            scaled_loss.backward()
                    else:
                        loss.backward()

        # neck_score = neck_score.unsqueeze(0)
        # neck_score = torch.nn.functional.interpolate(
        #     input=neck_score,
        #     scale_factor=[1, 4],
        #     mode="nearest")
        # backbone_score = backbone_score.unsqueeze(0)
        # backbone_score = torch.nn.functional.interpolate(
        #     input=backbone_score,
        #     scale_factor=[1, 4],
        #     mode="nearest")
            
        with torch.no_grad():
            if self.post_processing.init_flag is not True:
                self.post_processing.init_scores(sliding_num, len(vid_list))
                self.current_step_vid_list = vid_list
            self.seg_acc += self.post_processing.update(head_score, labels, idx) / sliding_num

            if self.runner_mode in ['train', 'validation']:
                # logger loss
                self.videos_loss = self.videos_loss + loss.detach().clone()
                self.video_backbone_loss = self.video_backbone_loss + backone_loss.detach().clone() / sliding_num
                self.video_neck_loss = self.video_neck_loss + neck_loss.detach().clone() / sliding_num
                self.video_head_loss = self.video_head_loss + head_loss.detach().clone() / sliding_num

    def run_one_iter(self, data, r_tic=None, epoch=None):
        # videos sliding stream train
        if self.runner_mode in ['train', 'validation']:
            self.record_dict['reader_time'].update(time.time() - r_tic)

        for sliding_seg in data:
            imgs, labels, masks, vid_list, sliding_num, step, idx = sliding_seg
            # wheather next step
            if self.current_step != step:
                self.batch_end_step(sliding_num=sliding_num, vid_list=vid_list, step=step, epoch=epoch)

            if idx >= 0: 
                self.run_one_clip(imgs, labels, masks, vid_list, sliding_num, idx)