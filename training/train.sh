#!/usr/bin/env bash
# Supervised fine-tuning of Qwen3-VL on MapVQA with the official Qwen3-VL fine-tuning code.
#
# Usage:  bash /path/to/MapVQA/training/train.sh <dataset_name> [base_model] [output_dir]
#   dataset_name  name registered in qwenvl/data/__init__.py
#   base_model    default Qwen/Qwen3-VL-4B-Instruct
#   output_dir    default ./checkpoints/<dataset_name>_<model>
set -euo pipefail

DATASET="${1:?usage: train.sh <dataset_name> [base_model] [output_dir]}"
MODEL="${2:-Qwen/Qwen3-VL-4B-Instruct}"
OUTPUT_DIR="${3:-./checkpoints/${DATASET}_$(basename "$MODEL")}"

# Hyperparameters used in the paper.
# Learning rate differs per target format: answer-only used 4e-5, rcot used 9e-5.
LR="${LR:-4e-5}"
EPOCHS=5
BATCH_SIZE=8
GRAD_ACCUM=4
MAX_LEN=6144
WEIGHT_DECAY=0.01

# The paper run used 4 GPUs: effective batch = 128.
NPROC_PER_NODE="${NPROC_PER_NODE:-4}"
MASTER_ADDR="${MASTER_ADDR:-127.0.0.1}"
MASTER_PORT="${MASTER_PORT:-$(shuf -i 20001-29999 -n 1)}"

torchrun --nproc_per_node="$NPROC_PER_NODE" --master_addr="$MASTER_ADDR" --master_port="$MASTER_PORT" \
  qwenvl/train/train_qwen.py \
  --model_name_or_path "$MODEL" \
  --dataset_use "$DATASET" \
  --data_flatten True \
  --tune_mm_vision False \
  --tune_mm_mlp True \
  --tune_mm_llm True \
  --bf16 \
  --output_dir "$OUTPUT_DIR" \
  --num_train_epochs "$EPOCHS" \
  --per_device_train_batch_size "$BATCH_SIZE" \
  --per_device_eval_batch_size $((BATCH_SIZE * 2)) \
  --gradient_accumulation_steps "$GRAD_ACCUM" \
  --max_pixels 50176 \
  --min_pixels 784 \
  --eval_strategy no \
  --save_strategy steps \
  --save_steps 200 \
  --save_total_limit 20 \
  --learning_rate "$LR" \
  --weight_decay "$WEIGHT_DECAY" \
  --warmup_ratio 0.03 \
  --max_grad_norm 1 \
  --lr_scheduler_type cosine \
  --logging_steps 1 \
  --model_max_length "$MAX_LEN" \
  --gradient_checkpointing True \
  --dataloader_num_workers 4 \
  --run_name "$(basename "$OUTPUT_DIR")" \
  --report_to "${REPORT_TO:-wandb}"
