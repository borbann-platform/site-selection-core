# Notebooks

Jupyter notebooks for training and experimenting with HGT property valuation models.

## Directory Structure

```
notebooks/
├── README.md                 # This file
├── train_hgt_tpu.ipynb       # TPU training on Google Colab
└── (future notebooks...)
```

## Notebooks

### 🚀 train_hgt_tpu.ipynb

**Purpose:** Train HGT model on Google Colab with TPU acceleration.

**Features:**
- Auto-detects TPU/GPU/CPU runtime
- Installs PyTorch/XLA for TPU support
- Uploads pre-built graph data
- Defines HGT model inline (no external dependencies)
- Training with early stopping
- Cold-start vs warm node analysis
- Visualization and model export

**Usage:**

1. **Prepare data locally:**
   ```bash
   cd gis-server
   python -m scripts.build_h3_features
   python -m scripts.train_hex2vec
   python -m scripts.build_hetero_graph
   ```

2. **Upload to Colab:**
   - Open [Google Colab](https://colab.research.google.com/)
   - Upload `train_hgt_tpu.ipynb`
   - Set runtime to TPU: `Runtime → Change runtime type → TPU`

3. **Run notebook:**
   - Upload `data/hetero_graph.pt` when prompted
   - Execute cells sequentially
   - Download trained model at the end

4. **Deploy locally:**
   ```bash
   unzip hgt_valuator.zip -d gis-server/models/hgt_valuator
   uvicorn main:app --reload
   ```

## Requirements

### Local (data preparation)
- Python 3.11+
- Dependencies in `pyproject.toml`

### Colab
- Google account with Colab access
- TPU runtime (optional but recommended)
- ~2GB RAM for typical graph sizes

## Tips

### TPU Performance
- TPUs work best with large batch sizes
- Sparse operations (used in GNNs) may not see full TPU benefit
- Consider GPU (A100) if TPU performance disappointing

### Memory Issues
If you encounter OOM errors:
1. Reduce `hidden_dim` from 128 to 64
2. Reduce `num_layers` from 2 to 1
3. Use mini-batch training with `NeighborLoader` (requires code modification)

### Debugging
Run cells one-by-one. If training hangs:
```python
# Add this after XLA operations:
import torch_xla.debug.metrics as met
print(met.metrics_report())
```
