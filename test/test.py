import os
import sys

current_dir= os.path.dirname(os.path.realpath(__file__))
work_folder=current_dir[:current_dir.find('test')]
sys.path.append(work_folder+'src/algorithm')
sys.path.append(work_folder+'src/config')
sys.path.append(work_folder+'src/data')
sys.path.append(work_folder+'src/tool')

import unittest

import torch
from config import get_default_config
from feature_extractor import FeatureExtractorFactory, VGG16FeatureExtractor
from rpn.anchor_creator import AnchorCreator
from rpn.anchor_target_creator import AnchorTargetCreator
from rpn.proposal_creator import ProposalCreator
from rpn.proposal_target_creator import ProposalTargetCreator
from rpn.region_proposal_network import RPN
from rpn.region_proposal_network_loss import RPNLoss
from rpn.region_proposal_network_trainer import RPNTrainer

from torch.utils.tensorboard import SummaryWriter
from torchsummary import summary
from utility import Utility
from visual_tool import draw_img_bboxes_labels
from voc_dataset import VOCDataset

from fast_rcnn.fast_rcnn_network import FastRCNN

IMG    =  torch.randn(1, 3, 800,800).float()
IMG_WIDTH = IMG.shape[-1]
IMG_HEIGHT = IMG.shape[-2]
BBOX   =  torch.FloatTensor([[20, 30, 400, 500], [300, 400, 500, 600]])
LABELS =  torch.LongTensor([6, 8])  
FEATURE_STRIDE = 16 

FEATURE_HEIGHT = int(IMG_HEIGHT / FEATURE_STRIDE)
FEATURE_WIDTH  = int(IMG_WIDTH / FEATURE_STRIDE)

IN_CHANNEL = 4096
NUM_CLASSES = 21
ROI_SIZE = 7



config = get_default_config()

@unittest.skip("passed")
class TestConfig(unittest.TestCase):
    def test_get_default_config(self) -> None:        
        print(config)
    

@unittest.skip("Passed")
class TestAnchorCreator(unittest.TestCase):
    def setUp(self) -> None:
        self.achor_creator = AnchorCreator(config)
    
    
    def test_anchor_base(self):
        self.assertEqual(self.achor_creator.anchor_base.shape,torch.Size([9, 4]))
    
    
    def test_anchor_creation(self):
        anchors = self.achor_creator.generate(2,2)
        print(anchors.shape)
        print(anchors)

@unittest.skip("Passed")
class TestUtility(unittest.TestCase):
    def test_loc_transform(self):
        src_bbox = torch.tensor([[0, 0, 20, 10], [5, 5, 50, 10]])
        loc = torch.tensor([[0.1, 0.3, 0.8, 0.2], [0.3, 0.7, 0.4, 0.9]])
        dst_bbox = Utility.loc2bbox(src_bbox, loc)

        locs_back = Utility.bbox2loc(src_bbox, dst_bbox)   
        self.assertTrue(torch.allclose(loc, locs_back))

@unittest.skip("Passed")
class TestAnchorTargetCreator(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor_creator = AnchorCreator(config)
        self.anchor_target_creator = AnchorTargetCreator(config)
        self.feature_extractor = FeatureExtractorFactory.create_feature_extractor('vgg16')
    
    def test_anchor_target_creator_2226(self):
        self.voc_dataset = VOCDataset(config)
        image,bboxes,lables,diff,img_file= self.voc_dataset[2225]
        image = image.unsqueeze(0)
        feature = self.feature_extractor(image.float())
        feature_height,feature_width = feature.shape[2:]
        anchors_of_img = self.anchor_creator.generate(feature_height,feature_width)
        img_height,img_width = image.shape[2:]
        target_labels,target_locs = self.anchor_target_creator.generate(anchors_of_img,bboxes,img_height,img_width)
        self.assertEqual((target_labels==1).nonzero().squeeze().shape,torch.Size([128]))
                    
    @unittest.skip("Passed")
    def test_anchor_target_creator(self):
        anchors_of_img = self.anchor_creator.generate(FEATURE_HEIGHT,FEATURE_WIDTH)
        self.assertEqual(anchors_of_img.shape, torch.Size([FEATURE_WIDTH*FEATURE_HEIGHT*9, 4]))
        
        lables,locs = self.anchor_target_creator.generate(anchors_of_img, BBOX,IMG_HEIGHT, IMG_WIDTH)
        
        if lables is not None:
            self.assertEqual(locs.shape, torch.Size([FEATURE_WIDTH*FEATURE_HEIGHT*9, 4]))
            self.assertEqual(lables.shape, torch.Size([FEATURE_WIDTH*FEATURE_HEIGHT*9]))
    
@unittest.skip("Passed")
class TestProposalCreator(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_extractor = FeatureExtractorFactory().create_feature_extractor("vgg16")
        self.anchor_creator = AnchorCreator(config)
        self.proposal_creator = ProposalCreator(config)
        self.rpn = RPN(config)
    
    def test_rpn(self):
        predcited_locs, predcited_scores = self.rpn(self.feature_extractor(IMG))
        anchors_of_img = self.anchor_creator.generate(FEATURE_HEIGHT,FEATURE_WIDTH)
        roi = self.proposal_creator.generate(anchors_of_img, predcited_locs[0], predcited_scores[0], IMG_HEIGHT, IMG_WIDTH)
        print(roi.shape)

@unittest.skip('passed')
class TestFeatureExtractor(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = FeatureExtractorFactory()
        
    def test_vgg16_extractor(self):
        extractor = self.factory.create_feature_extractor('vgg16')
        self.assertTrue(isinstance(extractor, VGG16FeatureExtractor))

    def test_vgg16_extractor_forward(self):
        extractor = self.factory.create_feature_extractor('vgg16')
        features = extractor(IMG)
        self.assertTrue(features.shape == torch.Size([1, 512, 50, 50]))   


@unittest.skip('passed')
class TestRPN(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_extractor= FeatureExtractorFactory().create_feature_extractor('vgg16')
        self.feature = self.feature_extractor(IMG)
        self.rpn = RPN(config)
        #summary(self.rpn, (3, 800, 800),device='cpu')
        
    def test_rpn_forward(self):
        predicted_scores,predicted_locs = self.rpn(self.feature)
        self.assertEqual(predicted_scores.shape, torch.Size([1, 18,50,50]))
        self.assertEqual(predicted_locs.shape,   torch.Size([1, 36,50,50]))
        
@unittest.skip('passed')
class TestRPNLoss(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_extractor= FeatureExtractorFactory().create_feature_extractor('vgg16')
        self.feature = self.feature_extractor(IMG)
        self.rpn = RPN(config)
        self.rpn_loss = RPNLoss(config)
        self.anchor_creator = AnchorCreator(config)
        self.anchor_target_creator = AnchorTargetCreator(config)
        
    def test_rpn_loss(self):
        predicted_scores,predicted_locs = self.rpn(self.feature)
        anchors_of_img = self.anchor_creator.generate(FEATURE_HEIGHT,FEATURE_WIDTH)
        target_lables,target_locs = self.anchor_target_creator.generate(anchors_of_img, BBOX,IMG_HEIGHT, IMG_WIDTH)

        if target_lables is not None:
            cls_loss,reg_loss = self.rpn_loss(predicted_scores[0],predicted_locs[0],target_lables,target_locs)
            print(cls_loss)
            print(reg_loss)

@unittest.skip('passed')
class TestVOCDataset(unittest.TestCase):
    def setUp(self) -> None:
        self.voc_dataset = VOCDataset(config)
        self.writer = SummaryWriter(config.TEST.TEMP_DIR)

    def tearDown(self) -> None:
        self.writer.flush()
        self.writer.close()
        return super().tearDown()

    def test_voc_dataset(self):
        print(self.voc_dataset.__len__())
        
        samples = 1
        imgs=torch.zeros([samples,3,500,500])       
        for i in range(samples):
            image,bboxes,lables,diff,img_file= self.voc_dataset[1430]
            print(image.shape)
            print(bboxes.shape)
            print(lables.shape)
            print(diff.shape)
            print(img_file)

        
            lable_names = [VOCDataset.VOC_BBOX_LABEL_NAMES[i] for i in lables]
            img_and_bbox = draw_img_bboxes_labels(image=image, bboxes=bboxes,labels=lable_names)
            imgs[i,:,:,:] = img_and_bbox

        self.writer.add_images('image',imgs,) 

@unittest.skip('testing')
class TestRPNTrainer(unittest.TestCase):
    def setUp(self):
        self.voc_dataset = VOCDataset(config)
        self.writer = SummaryWriter(config.TEST.TEMP_DIR)
        device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        self.trainer = RPNTrainer(config,self.voc_dataset,writer=self.writer,device=device)
        
    def test_train(self):
        self.trainer.train()

@unittest.skip('tested')
class TestProposalCreator(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_extractor = FeatureExtractorFactory().create_feature_extractor('vgg16')
        self.rpn = RPN(config)
        self.proposal_creator = ProposalCreator(config)
        self.anchor_creator = AnchorCreator(config)

    
    def test_generate(self):
        feature= self.feature_extractor(IMG)
        predicted_locs, predicted_scores = self.rpn(feature)
        anchors_of_img = self.anchor_creator.generate(FEATURE_HEIGHT,FEATURE_WIDTH)
        proposed_roi_bboxes =self.proposal_creator.generate(anchors_of_img,predicted_locs[0],predicted_scores[0],FEATURE_HEIGHT,FEATURE_WIDTH,IMG_HEIGHT,IMG_WIDTH)
        print(proposed_roi_bboxes.shape)

@unittest.skip('passed')
class TestProposalTargetCreator(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_extractor = FeatureExtractorFactory().create_feature_extractor('vgg16')
        self.rpn = RPN(config)
        self.anchor_creator = AnchorCreator(config)
        self.proposal_creator = ProposalCreator(config)
        self.anchor_target_creator = ProposalTargetCreator(config)
    
    def test_generate(self):
        feature= self.feature_extractor(IMG)
        predicted_locs, predicted_scores = self.rpn(feature)
        anchors_of_img = self.anchor_creator.generate(FEATURE_HEIGHT,FEATURE_WIDTH)
        proposed_roi_bboxes =self.proposal_creator.generate(anchors_of_img,predicted_locs[0],predicted_scores[0],FEATURE_HEIGHT,FEATURE_WIDTH,IMG_HEIGHT,IMG_WIDTH)
        roi,gt_roi_loc,gt_roi_label = self.anchor_target_creator.generate(proposed_roi_bboxes,BBOX,LABELS)
        print(roi.shape)
        print(gt_roi_loc.shape)
        print(gt_roi_label)

unittest.skip('passed')
class TestFastRCNN(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_extractor = FeatureExtractorFactory().create_feature_extractor('vgg16')
        self.rpn = RPN(config)
        self.fast_rcnn = FastRCNN(config)
        self.anchor_creator = AnchorCreator(config)
        self.proposal_creator = ProposalCreator(config)
        self.anchor_target_creator = ProposalTargetCreator(config)
    
    def test_forward(self):
        feature= self.feature_extractor(IMG)
        predicted_locs, predicted_scores = self.rpn(feature)
        anchors_of_img = self.anchor_creator.generate(FEATURE_HEIGHT,FEATURE_WIDTH)
        
        proposed_roi_bboxes =self.proposal_creator.generate(anchors_of_img,predicted_locs[0],predicted_scores[0],FEATURE_HEIGHT,FEATURE_WIDTH,IMG_HEIGHT,IMG_WIDTH)
        print('Proposed ROI BBOXES Size:{}'.format(proposed_roi_bboxes.shape))

        sampled_roi,gt_roi_loc,gt_roi_label = self.anchor_target_creator.generate(proposed_roi_bboxes,BBOX,LABELS)
        print('Sampled ROI Size:{}'.format(sampled_roi.shape))
        print('GT ROI LOC Size:{}'.format(gt_roi_loc.shape))
        print('GT ROI LABEL Size:{}'.format(gt_roi_label.shape))

        sampled_roi_bbox_indices = torch.zeros(len(sampled_roi))
        predicted_roi_cls_loc,predicted_roi_cls_score = self.fast_rcnn(feature,sampled_roi,sampled_roi_bbox_indices)

        print('Predicted ROI CLS LOC Size:{}'.format(predicted_roi_cls_loc.shape))
        print('Predicted ROI CLS SCORE Size:{}'.format(predicted_roi_cls_score.shape))

        




    
    

if __name__ == "__main__":
    print("Running RPN test:")
    unittest.main()
