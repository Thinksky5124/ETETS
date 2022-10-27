'''
Author       : Thyssen Wen
Date         : 2022-06-06 20:19:35
LastEditors  : Thyssen Wen
LastEditTime : 2022-10-26 13:15:03
Description  : Joint Head Modules
FilePath     : /SVTAS/model/heads/joint/__init__.py
'''
from .transducer_joint_head import TransudcerJointNet
from .transeger_fc_joint_head import TransegerFCJointNet
from .transeger_memory_tcn_joint_head import TransegerMemoryTCNJointNet
from .transeger_transformer_joint_head import TransegerTransformerJointNet
from .bridge_fusion_earlyhyp import BridgePromptFusionEarlyhyp

__all__ = [
    "TransudcerJointNet", "TransegerFCJointNet", "TransegerMemoryTCNJointNet",
    "TransegerTransformerJointNet", "BridgePromptFusionEarlyhyp"
]