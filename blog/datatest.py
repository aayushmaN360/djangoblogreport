import pandas as pd

df = pd.read_csv("balanced_3class_toxic_dataset.csv")
print(df.shape)
print(df.head())
print(df.iloc[0]['comment_text'])
