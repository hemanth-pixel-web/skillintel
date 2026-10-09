import re
import random
from collections import Counter

STOPWORDS = {
    "the","and","for","with","that","this","from","are","was","were","into","their",
    "have","has","will","can","not","but","its","using","used","use","about","which",
    "than","also","through","these","those","such","more","most","each","when","where",
    "what","how","why","who","a","an","of","to","in","on","is","by","as","or","at",
    "be","it","we","our","they","them","may","should","must","one","two","three"
}

def clean_text(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text

def sentences(text):
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    good = [p.strip() for p in parts if 45 <= len(p.strip()) <= 280]
    if len(good) >= 3:
        return good
    # Fallback for shorter text (e.g. a course title+description): relax the
    # minimum length so short but valid sentences can still form questions.
    return [p.strip() for p in parts if 20 <= len(p.strip()) <= 280]

def keywords(text, limit=15):
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text.lower())
    counts = Counter(w for w in words if w not in STOPWORDS)
    return [w for w, _ in counts.most_common(limit)]

def generate_mcqs(text, count=5):
    sents = sentences(text)
    keys = keywords(text, 20)
    if not sents:
        sents = [clean_text(text)] if clean_text(text) else []
    if not sents:
        return []

    questions = []
    used = set()
    rng = random.Random(42)

    for idx, sentence in enumerate(sents):
        if len(questions) >= count:
            break
        local_words = re.findall(r"[A-Za-z][A-Za-z0-9-]{4,}", sentence)
        candidates = [w for w in local_words if w.lower() not in STOPWORDS]
        if not candidates:
            continue
        answer = max(candidates, key=len)
        if answer.lower() in used:
            continue
        used.add(answer.lower())

        pattern = re.compile(re.escape(answer), re.I)
        blanked = pattern.sub("_____", sentence, count=1)
        distractors = [k for k in keys if k.lower() != answer.lower() and k.lower() not in sentence.lower()]
        distractors = distractors[:3]
        while len(distractors) < 3:
            distractors.append(["sampling","metadata","validation","indicator","dashboard","dataset"][len(distractors)])

        options = [answer] + distractors[:3]
        rng.shuffle(options)
        labels = ["A","B","C","D"]
        answer_label = labels[options.index(answer)]

        questions.append({
            "question": f"According to the learning material, which term best completes the statement: {blanked}",
            "options": dict(zip(labels, options)),
            "answer": answer_label,
            "explanation": f"The source material states: {sentence}",
            "skill": infer_skill(text)
        })

    return questions

def infer_skill(text):
    t = text.lower()
    mapping = [
        (("python","pandas","programming"), "Python for Statistics"),
        (("sql","database","query"), "SQL & Data Management"),
        (("survey","sampling","questionnaire"), "Data Collection & Survey Design"),
        (("visual","chart","dashboard"), "Data Visualization"),
        (("quality","validation","consistency"), "Data Quality"),
        (("official statistics","national statistics","census"), "Official Statistics"),
        (("artificial intelligence"," ai ","machine learning"), "AI & Responsible Use"),
        (("mean","regression","correlation","variance","statistical"), "Statistical Analysis")
    ]
    for terms, skill in mapping:
        if any(term in f" {t} " for term in terms):
            return skill
    return "Statistical Analysis"

def analyze_gaps(skills):
    gaps = []
    for s in skills:
        gap = max(0, s["target"] - s["score"])
        if gap >= 10:
            gaps.append({**s, "gap": round(gap, 1)})
    return sorted(gaps, key=lambda x: x["gap"], reverse=True)

def recommendation_reason(skill, score):
    if score < 50:
        return f"Priority: foundational learning is recommended because your current score is {score:.0f}%."
    if score < 70:
        return f"Focus area: strengthen practical application; your current score is {score:.0f}%."
    return f"Refinement: continue advanced practice to move from {score:.0f}% toward the 80% target."
