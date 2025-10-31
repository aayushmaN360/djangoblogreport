import pandas as pd

# Path to your dataset
DATASET_PATH = "toxic_dataset.csv"

# Load dataset
df = pd.read_csv(DATASET_PATH)

# Normalize column names
df.columns = [col.strip().lower() for col in df.columns]

# Check that required columns exist
if 'label' not in df.columns:
    print("❌ No 'label' column found. Available columns:", df.columns)
else:
    print(f"✅ Loaded dataset with {len(df)} rows.\n")
    print("📊 Unique labels and their counts:\n")
    print(df['label'].value_counts())

    print("\n🧩 Unique label names:")
    print(df['label'].unique())
