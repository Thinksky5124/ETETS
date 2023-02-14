'''
Author       : Thyssen Wen
Date         : 2022-11-16 16:18:28
LastEditors  : Thyssen Wen
LastEditTime : 2023-02-10 14:09:38
Description  : file content
FilePath     : /SVTAS/config/svtas/rgb/tsm_asrf_gtea.py
'''
_base_ = [
    '../../_base_/schedules/optimizer/adamw.py', '../../_base_/schedules/lr/liner_step_50e.py',
    '../../_base_/default_runtime.py', '../../_base_/collater/stream_compose.py',
    '../../_base_/dataset/gtea/gtea_stream_video.py'
]

num_classes = 11
sample_rate = 2
clip_seg_num = 64
ignore_index = -100
sliding_window = clip_seg_num * sample_rate
split = 1
batch_size = 1
epochs = 50

model_name = "TSM_ASRF_"+str(clip_seg_num)+"x"+str(sample_rate)+"_gtea_split" + str(split)

MODEL = dict(
    architecture = "Recognition2D",
    backbone = dict(
        name = "MobileNetV2TSM",
        pretrained = "./data/checkpoint/tsm_mobilenetv2_dense_320p_1x1x8_100e_kinetics400_rgb_20210202-61135809.pth",
        clip_seg_num = clip_seg_num,
        shift_div = 8,
        out_indices = (7, )
    ),
    neck = dict(
        # name = "TaskFusionPoolNeck",
        # num_classes=num_classes,
        # in_channels = 1280,
        # clip_seg_num = clip_seg_num,
        # need_pool = True,
        # fusion_ratio = 0.0
        name = "PoolNeck",
        in_channels = 1280,
        clip_seg_num = clip_seg_num,
        need_pool = True
    ),
    head = dict(
        name = "ActionSegmentRefinementFramework",
        in_channel = 1280,
        num_features = 64,
        num_stages = 4,
        num_layers = 10,
        num_classes = num_classes,
        sample_rate = sample_rate
    ),
    loss = dict(
        # name = "StreamSegmentationLoss",
        # backbone_loss_cfg = dict(
        #     name = "SegmentationLoss",
        #     num_classes = num_classes,
        #     sample_rate = sample_rate,
        #     smooth_weight = 0.0,
        #     ignore_index = -100
        # ),
        # head_loss_cfg = dict(
        #     name = "ASRFLoss",
        #     class_weight = [0.40253314,0.6060787,0.41817436,1.0009843,1.6168522,
        #                     1.2425169,1.5743035,0.8149039,7.6466165,1.0,0.29321033],
        #     pos_weight = [33.866594360086765],
        #     num_classes = num_classes,
        #     sample_rate = sample_rate,
        #     ignore_index = -100
        # )
        name = "ASRFLoss",
        class_weight = [0.40253314,0.6060787,0.41817436,1.0009843,1.6168522,
                        1.2425169,1.5743035,0.8149039,7.6466165,1.0,0.29321033],
        pos_weight = [33.866594360086765],
        num_classes = num_classes,
        sample_rate = sample_rate,
        ignore_index = -100
    )      
)

POSTPRECESSING = dict(
    name = "StreamScorePostProcessingWithRefine",
    sliding_window = sliding_window,
    ignore_index = ignore_index,
    refine_method_cfg = dict(
        name = "ASRFRefineMethod",
        refinement_method="refinement_with_boundary",
        boundary_threshold=0.5,
        theta_t=15,
        kernel_size=15
    )
)

LRSCHEDULER = dict(
    step_size = [epochs]
)

OPTIMIZER = dict(
    learning_rate = 0.0005,
    weight_decay = 1e-5,
    betas = (0.9, 0.999),
    need_grad_accumulate = True,
    finetuning_scale_factor=0.5,
    no_decay_key = [],
    finetuning_key = [],
    freeze_key = [],
)

DATASET = dict(
    temporal_clip_batch_size = 3,
    video_batch_size = batch_size,
    num_workers = batch_size,
    train = dict(
        file_path = "./data/gtea/splits/train.split" + str(split) + ".bundle",
        sliding_window = sliding_window
    ),
    test = dict(
        file_path = "./data/gtea/splits/test.split" + str(split) + ".bundle",
        sliding_window = sliding_window
    )
)

METRIC = dict(
    TAS = dict(
    file_output = False,
    score_output = False),
)

PIPELINE = dict(
    train = dict(
        name = "BasePipline",
        decode = dict(
            name="VideoDecoder",
            backend=dict(
                    name='DecordContainer')
        ),
        sample = dict(
            name = "VideoStreamSampler",
            is_train = True,
            sample_rate_dict={"imgs":sample_rate,"labels":sample_rate},
            clip_seg_num_dict={"imgs":clip_seg_num ,"labels":clip_seg_num},
            sliding_window_dict={"imgs":sliding_window,"labels":sliding_window},
            sample_add_key_pair={"frames":"imgs"},
            sample_mode = "uniform"
        ),
        transform = dict(
            name = "VideoTransform",
            transform_dict = dict(
                imgs = [
                dict(ResizeImproved = dict(size = 256)),
                dict(RandomCrop = dict(size = 224)),
                dict(RandomHorizontalFlip = None),
                dict(PILToTensor = None),
                dict(ToFloat = None),
                dict(Normalize = dict(
                    mean = [140.39158961711036, 108.18022223151027, 45.72351736766547],
                    std = [33.94421369129452, 35.93603536756186, 31.508484434367805]
                ))
            ])
        )
    ),
    test = dict(
        name = "BasePipline",
        decode = dict(
            name="VideoDecoder",
            backend=dict(
                    name='DecordContainer')
        ),
        sample = dict(
            name = "VideoStreamSampler",
            is_train = False,
            sample_rate_dict={"imgs":sample_rate,"labels":sample_rate},
            clip_seg_num_dict={"imgs":clip_seg_num ,"labels":clip_seg_num},
            sliding_window_dict={"imgs":sliding_window,"labels":sliding_window},
            sample_add_key_pair={"frames":"imgs"},
            sample_mode = "uniform"
        ),
        transform = dict(
            name = "VideoTransform",
            transform_dict = dict(
                imgs = [
                dict(ResizeImproved = dict(size = 256)),
                dict(CenterCrop = dict(size = 224)),
                dict(PILToTensor = None),
                dict(ToFloat = None),
                dict(Normalize = dict(
                    mean = [140.39158961711036, 108.18022223151027, 45.72351736766547],
                    std = [33.94421369129452, 35.93603536756186, 31.508484434367805]
                ))
            ])
        )
    )
)
