"""Evaluation pipeline of the frozen protocol: unit metrics, C5 freeze, analyses, figures.

Pure functions over probabilities, masks and unit tables; the GPU-bound part
(nnU-Net prediction) is isolated in ``study.nnunet_inference`` behind the
``Predictor`` protocol of ``study.inference``.
"""
