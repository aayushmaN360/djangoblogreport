# File: train_model.py (FINAL CLEANED VERSION for Balanced 2-Class Data)
import pandas as pd
import numpy as np
import re
import pickle
from collections import Counter
import os

print("--- FINAL SCRIPT: Training on a Pre-Balanced 2-Class Dataset ---")

# ==============================================================================
#  1. DEFINE FILE PATHS AND LOAD DATA
# ==============================================================================
script_dir = os.path.dirname(os.path.abspath(__file__))
# INPUT: Your perfectly balanced 2-class dataset file
DATASET_PATH = os.path.join(script_dir, 'toxic_dataset.csv')
# OUTPUT: The name of the final model file
OUTPUT_MODEL_PATH = os.path.join(script_dir, '2_class_naive_bayes_model.pkl')

print(f"\nAttempting to load source dataset: {os.path.basename(DATASET_PATH)}")
try:
    df = pd.read_csv(DATASET_PATH)
    print(f"Successfully loaded dataset with {len(df)} rows.")
    print(f"Initial distribution:\n{df['label'].value_counts()}")
except FileNotFoundError:
    print(f"!!! ERROR: Could not find the dataset at '{DATASET_PATH}'. Please check the file name.")
    exit()

# ==============================================================================
#  2. TRAIN THE MODEL (Using all our best "from-scratch" techniques)
# ==============================================================================

# --- Preprocessing with bigrams for context ---
stop_words = {'i','me','my','myself','we','our','ourselves','you','your','yours','yourself','yourselves','he','him','his','himself','she','her','herself','it','its','itself','they','them','their','theirs','themselves','what','which','who','whom','this','that','these','those','am','is','are','was','were','be','been','being','have','has','had','having','do','does','did','doing','a','an','the','and','but','if','or','because','as','until','while','of','at','by','for','with','about','against','between','into','through','during','before','after','above','below','to','from','up','down','in','out','on','off','over','under','again','further','then','once','here','there','when','where','why','how','all','any','both','each','few','more','most','other','some','such','no','nor','not','only','own','same','so','than','too','very','can','will','just','don','should','now'}

def stem(word):
    suffixes = ['ing', 'ly', 'ed', 'ion', 's', 'er', 'es', 'est']
    for suffix in suffixes:
        if word.endswith(suffix) and len(word) > len(suffix) + 2: return word[:-len(suffix)]
    return word

def preprocess(text):
    text = str(text).lower(); text = re.sub(r'[^a-z\s]', '', text); tokens = text.split()
    unigrams = [stem(word) for word in tokens if word not in stop_words and len(word) > 1]
    bigrams = ['_'.join(pair) for pair in zip(unigrams, unigrams[1:])]
    return unigrams + bigrams

# --- Data Preparation ---
df.dropna(subset=['comment_text', 'label'], inplace=True)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)
split_idx = int(0.8 * len(df))
train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]
X_train, y_train = train_df['comment_text'].tolist(), train_df['label'].tolist()
X_test, y_test = test_df['comment_text'].tolist(), test_df['label'].tolist()
print("\nData loaded and split successfully.")

# --- Build Pruned Vocabulary (to reduce noise) ---
print("Building a pruned vocabulary...")
MIN_FREQUENCY = 5
all_tokens = [token for text in X_train for token in preprocess(text)]
feature_counts = Counter(all_tokens)
vocab = sorted([word for word, count in feature_counts.items() if count >= MIN_FREQUENCY])
word2idx = {word: i for i, word in enumerate(vocab)}
print(f"Vocabulary pruned. Final size is {len(vocab)}.")

# --- Train the Naive Bayes Model ---
print("Training 2-Class Naive Bayes model...")
classes = sorted(list(set(y_train)))
class_counts = Counter(y_train)
# No class weights are needed because the dataset is perfectly balanced
priors = {c: np.log(class_counts.get(c, 0) / len(y_train)) for c in classes}
alpha = 1
word_counts_per_class = {c: np.ones(len(vocab)) * alpha for c in classes}
total_words_per_class = {c: len(vocab) * alpha for c in classes}
for text, label in zip(X_train, y_train):
    for feature in preprocess(text):
        if feature in word2idx:
            word_counts_per_class[label][word2idx[feature]] += 1
            total_words_per_class[label] += 1
likelihoods = {c: np.log(word_counts_per_class[c] / total_words_per_class[c]) for c in classes}
print("Model training complete.")

# ==============================================================================
#  3. EVALUATE THE FINAL MODEL
# ==============================================================================
# (This section is important for you to see the final performance)
def predict(text):
    tokens = preprocess(text)
    class_scores = {c: priors[c] for c in classes}
    for feature in tokens:
        for c in classes:
            if feature in word2idx:
                class_scores[c] += likelihoods[c][word2idx[feature]]
            else:
                class_scores[c] += np.log(alpha / (total_words_per_class.get(c, 1) + 1))
    return max(class_scores, key=class_scores.get)

print("\nEVALUATING FINAL 2-CLASS MODEL ON TEST SET...")
y_pred = [predict(text) for text in X_test]
conf_matrix = {true_class: {pred_class: 0 for pred_class in classes} for true_class in classes}
for true_label, pred_label in zip(y_test, y_pred):
    if true_label in conf_matrix and pred_label in conf_matrix[true_label]:
        conf_matrix[true_label][pred_label] += 1
print("\n--- Confusion Matrix ---")
header = f"{'Actual ↓ | Predicted →':<20}" + " | ".join([f"{c:<15}" for c in classes]); print(header); print("-" * len(header))
for true_class in classes:
    row = [str(conf_matrix[true_class][pred_class]) for pred_class in classes]
    print(f"{true_class:<20}" + " | ".join([f"{r:<15}" for r in row]))
def safe_divide(numerator, denominator): return numerator / denominator if denominator != 0 else 0
metrics = {}
for c in classes:
    TP = conf_matrix[c][c]; FP = sum(conf_matrix[other_class][c] for other_class in classes if other_class != c)
    FN = sum(conf_matrix[c][other_class] for other_class in classes if other_class != c)
    precision = safe_divide(TP, TP + FP); recall = safe_divide(TP, TP + FN)
    f1_score = safe_divide(2 * precision * recall, precision + recall)
    metrics[c] = {'precision': precision, 'recall': recall, 'f1-score': f1_score}
print("\n--- Classification Report ---")
print(f"{'Class':<20}{'Precision':<15}{'Recall':<15}{'F1-Score':<15}"); print("---------------------------------------------------------------")
for c in classes:
    m = metrics[c]; print(f"{c:<20}{m['precision']:.4f}{m['recall']:<15.4f}{m['f1-score']:.4f}")
print("---------------------------------------------------------------")
total_correct = sum(conf_matrix[c][c] for c in classes); total_samples = len(y_test)
accuracy = safe_divide(total_correct, total_samples)
print(f"\nOverall Accuracy: {accuracy:.4f} ({total_correct} out of {total_samples} correct)")

# ==============================================================================
#  4. SAVE THE FINAL MODEL
# ==============================================================================
model_artifacts = {
    "word2idx": word2idx, "classes": classes, "priors": priors,
    "likelihoods": likelihoods, "total_words_per_class": total_words_per_class,
    "alpha": alpha, "stop_words": stop_words
}
with open(OUTPUT_MODEL_PATH, "wb") as f:
    pickle.dump(model_artifacts, f)
    
print(f"\n✅ Final 2-Class model trained and saved successfully to '{OUTPUT_MODEL_PATH}'")