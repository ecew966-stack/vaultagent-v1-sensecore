#!/bin/bash
# CCI 容器一键实验运行脚本
# 用法: bash scripts/run_all_experiments.sh [--mock] [--samples N]
set -e

MOCK=""
SAMPLES=50
EXTRA_ARGS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mock) MOCK="--mock"; shift ;;
    --samples) SAMPLES="$2"; shift 2 ;;
    --full) SAMPLES=200; shift ;;
    *) EXTRA_ARGS="$EXTRA_ARGS $1"; shift ;;
  esac
done

cd /root/vaultagent-v0.2-sensecore

echo "============================================"
echo "  VaultAgent 全量实验"
echo "  时间: $(date)"
echo "  样本数: $SAMPLES"
echo "  Mock: ${MOCK:-否}"
echo "============================================"

# 1. 系统检查
echo ""
echo "[1/6] 系统状态检查..."
python -c "
from src.core.settings import Settings
from src.agent.controller import VaultAgentController
s = Settings(_env_file='.env'); s.prepare_paths()
c = VaultAgentController(s)
st = c.system_status()
print(f'  环境: {st[\"environment\"]}')
print(f'  本地模型: {st[\"local_model\"][\"model\"]} | 可达: {st[\"local_model\"][\"reachable\"]}')
print(f'  云端模型: {st[\"cloud_model\"][\"model\"]} | 可达: {st[\"cloud_model\"][\"reachable\"]}')
print(f'  Mock: {st[\"mock_models_allowed\"]}')
"

# 2. Chroma 知识库检查
echo ""
echo "[2/6] Chroma 知识库检查..."
python -c "
from pathlib import Path
db = Path('/root/chroma_db')
if db.exists():
    from src.knowledge.chroma_adapter import ChromaDenseAdapter, ChromaAdapterConfig
    c = ChromaAdapterConfig(persist_directory=str(db))
    a = ChromaDenseAdapter(c)
    print(f'  Chroma 文档数: {a.count()}')
else:
    print('  Chroma DB 不存在，请先运行 deploy_chroma_kb.py')
"

# 3. 基线实验
echo ""
echo "[3/6] 基线对比实验..."
python experiments/full_experiment.py \
  --samples $SAMPLES \
  $MOCK \
  --baselines LOCAL_ONLY RAW_CLOUD_RAG CLOUD_PLAN VAULTAGENT \
  --output experiments/results

# 4. 攻击场景
echo ""
echo "[4/6] 攻击场景测试..."
python experiments/full_experiment.py \
  --samples 10 \
  $MOCK \
  --baselines VAULTAGENT \
  --output experiments/results/attacks

# 5. 消融实验
echo ""
echo "[5/6] 消融实验..."
python experiments/run_ablations.py $MOCK

# 6. 汇总
echo ""
echo "[6/6] 生成汇总报告..."
python -c "
import json, glob
from pathlib import Path

results_dir = Path('experiments/results')
csv_files = sorted(results_dir.glob('run_*.csv'), reverse=True)
json_files = sorted(results_dir.glob('run_*.jsonl'), reverse=True)

print('最近实验结果:')
for f in csv_files[:5]:
    print(f'  {f} ({f.stat().st_size} bytes)')

# 读取最新汇总
summary_files = sorted(results_dir.glob('*_summary.json'), reverse=True)
if summary_files:
    summary = json.loads(summary_files[0].read_text())
    print()
    print('=== 最新实验汇总 ===')
    for baseline, metrics in sorted(summary.items()):
        print(f'\n{baseline}:')
        for k, v in metrics.items():
            print(f'  {k}: {v}')
"

echo ""
echo "============================================"
echo "  实验完成: $(date)"
echo "  结果目录: experiments/results/"
echo "============================================"
