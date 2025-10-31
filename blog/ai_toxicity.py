# File: ai_toxicity.py (FINAL HYBRID VERSION with Allowlist Logic)
import pickle
import numpy as np
import re
from django.conf import settings
import os


class _BaseToxicityClassifier:
    """
    This INTERNAL class loads and runs the powerful 2-class statistical model.
    """
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(os.path.dirname(__file__), '2_class_naive_bayes_model.pkl') 
        
        self.NON_TOXIC_LABEL = 'non-toxic'
        self.model_loaded = False

        try:
            with open(model_path, 'rb') as f:
                artifacts = pickle.load(f)
            
            self.priors = artifacts['priors']
            self.likelihoods = artifacts['likelihoods']
            self.word2idx = artifacts['word2idx']
            self.classes = artifacts['classes']
            self.alpha = artifacts['alpha']
            self.total_words_per_class = artifacts['total_words_per_class']
            self.stop_words = artifacts['stop_words']

            self.model_loaded = True
            print(f"✅ AI Toxicity Engine loaded successfully from: {os.path.basename(model_path)}")
        except Exception as e:
            print(f"!!! AI MODEL ERROR: Could not load model file '{os.path.basename(model_path)}'. Predictions disabled. Error: {e}")

    def stem(self, word):
        suffixes = ['ing', 'ly', 'ed', 'ion', 's', 'er', 'es', 'est']
        for suffix in suffixes:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                return word[:-len(suffix)]
        return word

    def preprocess(self, text):
        text = str(text).lower()
        text = re.sub(r'[^a-z\s]', '', text)
        tokens = text.split()
        unigrams = [self.stem(word) for word in tokens if word not in self.stop_words and len(word) > 1]
        bigrams = ['_'.join(pair) for pair in zip(unigrams, unigrams[1:])]
        return unigrams + bigrams

    def predict(self, text):
        if not self.model_loaded:
            return False, self.NON_TOXIC_LABEL

        tokens = self.preprocess(text)
        class_scores = {c: self.priors[c] for c in self.classes}

        for feature in tokens:
            for c in self.classes:
                if feature in self.word2idx:
                    class_scores[c] += self.likelihoods[c][self.word2idx[feature]]
                else:
                    class_scores[c] += np.log(self.alpha / (self.total_words_per_class.get(c, 1) + 1))
        
        predicted_label = max(class_scores, key=class_scores.get)
        is_toxic = (predicted_label != self.NON_TOXIC_LABEL)
        
        return is_toxic, predicted_label


# --- NEW: Allowlist of Positive Words ---
SAFE_TRIGGERS = {
    'nepal', 'beautiful', 'country', 'love', 'amazing', 'wonderful',
    'thank you', 'thanks', 'appreciate', 'great', 'excellent'
}

# --- Rule-Based High-Toxicity Triggers ---
HIGHLY_TOXIC_TRIGGERS = {
    'idiot', 'moron', 'stupid', 'dumb', 'kill yourself', 'go die',
    'shut up', 'fuck you', 'bitch', 'asshole', 'machikney', 'muji'
}


class MainClassifier:
    """
    This is the public-facing classifier. It orchestrates the hybrid approach.
    """
    def __init__(self):
        self._base_classifier = _BaseToxicityClassifier()

    def predict(self, text):
        # 1️⃣ Get base model prediction
        is_problematic, initial_label = self._base_classifier.predict(text)

        if not is_problematic:
            return False, 'non-toxic'

        # 2️⃣ Allowlist safety check
        lower_comment = text.lower()
        safe_word_count = sum(1 for word in SAFE_TRIGGERS if word in lower_comment)
        if safe_word_count >= 2:
            # Comment contains enough positive/safe context words
            return False, 'non-toxic'

        # 3️⃣ Check for extreme toxicity triggers
        for trigger in HIGHLY_TOXIC_TRIGGERS:
            if trigger in lower_comment:
                return True, 'highly-toxic'

        # 4️⃣ Default case: moderately toxic
        return True, 'toxic'


# --- Final Singleton Instance ---
toxicity_classifier = MainClassifier()
