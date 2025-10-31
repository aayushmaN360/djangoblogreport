import pandas as pd

df = pd.read_csv("final_balanced_dataset.csv")

# Drop any accidental header rows
df = df[df['label'] != 'label']

# Drop duplicates
df.drop_duplicates(subset=['comment_text'], inplace=True)

df.to_csv("cleaned_dataset.csv", index=False)
print(f"Cleaned dataset saved with {len(df)} rows.")
