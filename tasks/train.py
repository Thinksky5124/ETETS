import os.path as osp
import time

import numpy as np
import torch
from utils.logger import get_logger, AverageMeter, log_batch
from utils.save_load import mkdir

from model.etets import ETETS
from model.loss import ETELoss
from dataset.segmentation_dataset import SegmentationDataset
from utils.metric import SegmentationMetric
from dataset.pipline import Pipeline


def train(cfg,
          weights=None,
          validate=True):
    """Train model entry
    """

    logger = get_logger("ETETS")
    batch_size = cfg.DATASET.get('batch_size', 8)
    valid_batch_size = cfg.DATASET.get('valid_batch_size', batch_size)

    # default num worker: 0, which means no subprocess will be created
    num_workers = cfg.DATASET.get('num_workers', 0)
    valid_num_workers = cfg.DATASET.get('valid_num_workers', num_workers)
    model_name = cfg.model_name
    output_dir = cfg.get("output_dir", f"./output")
    mkdir(output_dir)

    # 1.construct model
    model = ETETS(cfg.MODEL).cuda()
    criterion = ETELoss()

    # 2. build metirc
    Metric = SegmentationMetric(cfg.METRIC)

    # 3. Construct solver.
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.OPTIMIZER.learning_rate,
        betas=(0.9, 0.999), weight_decay=0.0005)

    # Resume
    resume_epoch = cfg.get("resume_epoch", 0)
    if resume_epoch:
        path_checkpoint = osp.join(output_dir,
                            model_name + f"_epoch_{resume_epoch:05d}" + ".pkl")
        checkpoint = torch.load(path_checkpoint)

        model.load_state_dict(checkpoint['net'])

        optimizer.load_state_dict(checkpoint['optimizer'])  # 加载优化器参数
        start_epoch = checkpoint['epoch']
    # 4. construct Pipeline
    data_Pipeline = Pipeline(cfg.PIPELINE.train)

    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=cfg.OPTIMIZER.step_size, gamma=cfg.OPTIMIZER.gamma)

    # 5. Train Model
    record_dict = {'batch_time': AverageMeter('batch_cost', '.5f'),
                   'reader_time': AverageMeter('reader_time', '.5f'),
                   'loss': AverageMeter('loss', '7.5f'),
                   'lr': AverageMeter('lr', 'f', need_avg=False),
                   'F1@0.5': AverageMeter("F1@0.50", '.5f'),
                   'cls_loss': AverageMeter("cls_loss", '.5f'),
                   'seg_loss': AverageMeter("seg_loss", '.5f')
                  }

    best = 0.0
    for epoch in range(0, cfg.epochs):
        if epoch < resume_epoch:
            logger.info(
                f"| epoch: [{epoch+1}] <= resume_epoch: [{ resume_epoch}], continue... "
            )
            continue

        model.train()

        # batch videos sampler
        for idx in range(0):
            tic = time.time()

            # 6. Construct dataset and dataloader
            train_dataset = torch.utils.data.DataLoader(
                SegmentationDataset(

                ),
                batch_size=batch_size,
                num_workers=num_workers,
                collate_fn_cfg=cfg.get('MIX', None),
                shuffle=False
            )

            # videos sliding stream train
            videos_loss = 0.
            for i, data in enumerate(train_loader):
                record_list['reader_time'].update(time.time() - tic)

                # train segment
                outputs = model(data)

                cls_loss = 0.
                seg_loss = 0.
                loss = outputs['loss'] / num_clip

                avg_loss.backward()
                post_precessing()
                videos_loss += loss.item()
                
        
            optimizer.step()
            optimizer.zero_grad()
            f1 = Metric.update(i, data, outputs)
            
            # logger
            record_list['batch_time'].update(time.time() - tic)
            record_list['loss'].update(videos_loss, batch_size)
            record_list['lr'].update(optimizer.state_dict()['param_groups'][0]['lr'], batch_size)
            record_list['F1@0.5'].update(f1, batch_size)
            record_list['cls_loss'].update(cls_loss, batch_size)
            record_list['seg_loss'].update(seg_loss, batch_size)
            tic = time.time()


            if i % cfg.get("log_interval", 10) == 0:
                ips = "ips: {:.5f} instance/sec.".format(
                    batch_size / record_list["batch_time"].val)
                log_batch(record_list, i, epoch + 1, cfg.epochs, "train", ips)

        # metric output
        Metric.accumulate()

        # update lr
        scheduler.step()
        ips = "avg_ips: {:.5f} instance/sec.".format(
            batch_size * record_list["batch_time"].count /
            record_list["batch_time"].sum)
        log_epoch(record_list, epoch + 1, "train", ips)

        def evaluate(best):
            model.eval()
            results = []
            record_dict = {'batch_time': AverageMeter('batch_cost', '.5f'),
                   'reader_time': AverageMeter('reader_time', '.5f'),
                   'loss': AverageMeter('loss', '7.5f'),
                   'F1@0.5': AverageMeter("F1@0.50", '.5f'),
                   'cls_loss': AverageMeter("cls_loss", '.5f'),
                   'seg_loss': AverageMeter("seg_loss", '.5f')
                  }
            
            tic = time.time()
            # batch videos sampler
            for idx in range(0):
                tic = time.time()
                valid_dataset = torch.utils.data.DataLoader(
                    SegmentationDataset(

                    ),
                    batch_size=batch_size,
                    num_workers=num_workers,
                    collate_fn_cfg=cfg.get('MIX', None),
                    shuffle=False
                )
                # videos sliding stream train
                videos_loss = 0.
                for i, data in enumerate(valid_dataset):
                    record_list['reader_time'].update(time.time() - tic)

                    # train segment
                    outputs = model(data)
                    cls_loss = 0.
                    seg_loss = 0.
                    loss = outputs['loss'] / num_clip

                    avg_loss.backward()
                    post_precessing()
                    videos_loss += loss.item()
                    
            
                optimizer.step()
                optimizer.zero_grad()
                f1 = Metric.update(i, data, outputs)
                
                # logger
                record_list['batch_time'].update(time.time() - tic)
                record_list['loss'].update(videos_loss, batch_size)
                record_list['F1@0.5'].update(f1, batch_size)
                record_list['cls_loss'].update(cls_loss, batch_size)
                record_list['seg_loss'].update(seg_loss, batch_size)
                tic = time.time()


                if i % cfg.get("log_interval", 10) == 0:
                    ips = "ips: {:.5f} instance/sec.".format(
                        batch_size / record_list["batch_time"].val)
                    log_batch(record_list, i, epoch + 1, cfg.epochs, "train", ips)

            # metric output
            Metric_dict = Metric.accumulate()

            ips = "avg_ips: {:.5f} instance/sec.".format(
                batch_size * record_list["batch_time"].count /
                record_list["batch_time"].sum)
            log_epoch(record_list, epoch + 1, "train", ips)

            best_flag = False
            if Metric_dict["F1@0.50"] > best:
                best = Metric_dict["F1@0.50"]
                best_flag = True
            return best, best_flag

        # 5. Validation
        if validate and (epoch % cfg.get("val_interval", 1) == 0
                         or epoch == cfg.epochs - 1):
            with torch.no_grad():
                best, save_best_flag = evaluate(best)
            # save best
            if save_best_flag:
                torch.save(model.state_dict(),
                     osp.join(output_dir, model_name + "_best.pkl"))
                logger.info(
                        f"Already save the best model (F1@0.50){int(best * 10000) / 10000}"
                    )

        # 6. Save model and optimizer
        if epoch % cfg.get("save_interval", 1) == 0 or epoch == cfg.epochs - 1:
            torch.save(
                model.state_dict(),
                osp.join(output_dir,
                         model_name + f"_epoch_{epoch + 1:05d}.pkl"))

    logger.info(f'training {model_name} finished')
