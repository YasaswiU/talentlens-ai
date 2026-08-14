"""
services/quiz_generator.py
-----------------------------
Adaptive 5-question multiple-choice quiz generation (Section 12).

Questions are drawn from a hand-curated bank keyed by skill name, so that
the quiz is "adaptive" in the sense that it reflects the specific
technical skills spaCy/the fallback extractor found on the candidate's
resume. If the candidate has fewer than 5 recognized skills, the bank
falls back to filling remaining slots with general technical questions so
the quiz always has exactly 5 questions.
"""

import random

# Each skill maps to a list of (question, option_a, option_b, option_c, option_d, correct_letter)
QUESTION_BANK = {
    "python": [
        ("Which keyword is used to define a function in Python?", "func", "def", "lambda", "function", "B"),
        ("What data type is returned by `range(5)` in Python 3?", "list", "tuple", "range object", "generator", "C"),
    ],
    "java": [
        ("Which keyword is used to inherit a class in Java?", "implements", "extends", "inherits", "super", "B"),
        ("What is the entry point method of a Java application?", "start()", "run()", "main()", "init()", "C"),
    ],
    "c++": [
        ("Which operator is used to allocate memory dynamically in C++?", "malloc", "new", "alloc", "create", "B"),
        ("What does STL stand for in C++?", "Standard Type Library", "Standard Template Library",
         "System Type Library", "Structured Template Library", "B"),
    ],
    "c#": [
        ("Which keyword prevents a class from being inherited in C#?", "static", "sealed", "final", "const", "B"),
    ],
    "javascript": [
        ("Which keyword declares a block-scoped variable in JavaScript?", "var", "let", "def", "static", "B"),
        ("What does `===` check for in JavaScript?", "value only", "type only",
         "value and type", "reference only", "C"),
    ],
    "typescript": [
        ("What is the main benefit TypeScript adds over JavaScript?", "Faster runtime", "Static typing",
         "Smaller file size", "Built-in database", "B"),
    ],
    "sql": [
        ("Which SQL clause is used to filter rows before grouping?", "HAVING", "WHERE", "GROUP BY", "ORDER BY", "B"),
        ("Which SQL command is used to remove a table entirely?", "DELETE", "TRUNCATE", "DROP", "REMOVE", "C"),
    ],
    "nosql": [
        ("Which of these is a key characteristic of NoSQL databases?", "Fixed schema", "Flexible/schema-less design",
         "Only supports SQL queries", "Requires foreign keys", "B"),
    ],
    "mongodb": [
        ("What is the basic unit of data storage in MongoDB called?", "Row", "Record", "Document", "Tuple", "C"),
    ],
    "postgresql": [
        ("PostgreSQL is best described as which type of database?", "Key-value store",
         "Object-relational database", "Graph database", "Document store", "B"),
    ],
    "mysql": [
        ("Which storage engine is the default in modern MySQL versions?", "MyISAM", "InnoDB", "Memory", "CSV", "B"),
    ],
    "redis": [
        ("Redis is primarily used as what type of store?", "Relational database",
         "In-memory key-value store", "Graph database", "Document store", "B"),
    ],
    "html": [
        ("Which HTML tag is used to create a hyperlink?", "<link>", "<a>", "<href>", "<url>", "B"),
    ],
    "css": [
        ("Which CSS property controls the text size?", "font-style", "text-size", "font-size", "text-style", "C"),
    ],
    "react": [
        ("What is used in React to manage component-level state?", "props", "useState hook", "context only", "redux only", "B"),
    ],
    "angular": [
        ("Angular applications are primarily built using which language?", "Python", "TypeScript", "Ruby", "Go", "B"),
    ],
    "vue": [
        ("Which directive in Vue is used for two-way data binding?", "v-bind", "v-model", "v-if", "v-for", "B"),
    ],
    "node.js": [
        ("Node.js is built on which JavaScript engine?", "SpiderMonkey", "V8", "Chakra", "JavaScriptCore", "B"),
    ],
    "express": [
        ("Express.js is a framework for which platform?", "Python", "Node.js", "Java", "PHP", "B"),
    ],
    "django": [
        ("Django follows which architectural pattern?", "MVC-VC", "MVT (Model-View-Template)", "MVP", "VIPER", "B"),
    ],
    "flask": [
        ("Flask is best described as what kind of framework?", "Full-stack, heavy", "Lightweight WSGI micro-framework",
         "Only for databases", "A JavaScript framework", "B"),
    ],
    "fastapi": [
        ("FastAPI is built on top of which components for speed?", "Django ORM", "Starlette and Pydantic",
         "Flask and Jinja2", "Node.js", "B"),
    ],
    "machine learning": [
        ("Which of these is a supervised learning task?", "Clustering", "Classification", "Dimensionality reduction", "Association mining", "B"),
        ("What is 'overfitting' in machine learning?", "Model performs well on unseen data",
         "Model memorizes training data but fails to generalize", "Model has too few parameters", "Model trains too fast", "B"),
    ],
    "deep learning": [
        ("What is the basic computational unit of a neural network called?", "Node cluster", "Neuron/unit", "Kernel", "Layer stack", "B"),
    ],
    "nlp": [
        ("What does NLP stand for in AI?", "Neural Language Programming", "Natural Language Processing",
         "Natural Logic Programming", "Node Language Protocol", "B"),
    ],
    "computer vision": [
        ("Which algorithm type is most commonly used for image classification?", "Decision trees only",
         "Convolutional Neural Networks (CNNs)", "Linear regression", "Apriori algorithm", "B"),
    ],
    "tensorflow": [
        ("TensorFlow was originally developed by which company?", "Meta", "Google", "Amazon", "Microsoft", "B"),
    ],
    "pytorch": [
        ("PyTorch was originally developed by which organization?", "Google", "Meta (Facebook) AI Research", "Microsoft", "OpenAI", "B"),
    ],
    "scikit-learn": [
        ("scikit-learn is primarily built on top of which libraries?", "TensorFlow and Keras",
         "NumPy, SciPy, and matplotlib", "Pandas only", "PyTorch", "B"),
    ],
    "aws": [
        ("Which AWS service provides scalable object storage?", "EC2", "S3", "Lambda", "RDS", "B"),
    ],
    "azure": [
        ("Azure Functions is Microsoft's offering for which computing model?", "Virtual machines", "Serverless computing", "Container orchestration only", "Static websites only", "B"),
    ],
    "gcp": [
        ("Which GCP service is used for running containerized applications at scale?", "BigQuery", "Google Kubernetes Engine (GKE)", "Cloud Storage", "Pub/Sub", "B"),
    ],
    "docker": [
        ("What file is used to define how a Docker image is built?", "docker-compose.yml", "Dockerfile", "manifest.json", "image.config", "B"),
    ],
    "kubernetes": [
        ("What is the smallest deployable unit in Kubernetes?", "Container", "Pod", "Node", "Cluster", "B"),
    ],
    "ci/cd": [
        ("What does CI/CD primarily help automate?", "UI design", "Build, test, and deployment pipelines", "Database backups only", "Password resets", "B"),
    ],
    "jenkins": [
        ("Jenkins is primarily used for what purpose?", "Version control", "Continuous integration/automation", "Cloud storage", "Load balancing", "B"),
    ],
    "git": [
        ("Which Git command creates a new branch?", "git branch <name>", "git commit -b", "git new <name>", "git init <name>", "A"),
    ],
    "linux": [
        ("Which command lists files in a Linux directory?", "dir", "ls", "list", "show", "B"),
    ],
    "php": [
        ("PHP code is typically embedded within which tags?", "<script>...</script>", "<?php ... ?>", "<py>...</py>", "<code>...</code>", "B"),
    ],
    "ruby": [
        ("Ruby on Rails follows which architectural pattern?", "MVVM", "MVC", "MVP", "Flux", "B"),
    ],
    "go": [
        ("The Go programming language was developed by which company?", "Microsoft", "Google", "Amazon", "Oracle", "B"),
    ],
    "rust": [
        ("Rust is best known in the industry for guaranteeing what, without a garbage collector?", "Faster networking",
         "Memory safety", "Smaller binaries only", "Built-in AI", "B"),
    ],
}

GENERAL_QUESTIONS = [
    ("What does 'API' stand for?", "Application Program Interface", "Application Programming Interface",
     "Applied Program Interface", "Automated Programming Interface", "B"),
    ("Which of these best describes version control?", "A backup tool for photos",
     "A system for tracking changes to code over time", "A database engine", "A styling framework", "B"),
    ("What is the primary purpose of unit testing?", "To test the entire deployed system",
     "To verify individual components work correctly in isolation", "To design the UI", "To manage servers", "B"),
    ("What does 'REST' stand for in RESTful APIs?", "Representational State Transfer",
     "Remote State Transfer", "Representational Server Transfer", "Reliable State Transfer", "A"),
    ("Which of these is a NoSQL database category?", "Relational", "Document-oriented", "Columnar-only SQL", "Tabular SQL", "B"),
]


def generate_quiz_questions(candidate_skills, question_count=5):
    """
    Build `question_count` MCQs based on the candidate's extracted skills.

    Returns list of dicts:
        {question, option_a, option_b, option_c, option_d, correct_answer, skill}
    """
    pool = []
    skills = [s.lower() for s in candidate_skills]
    random.shuffle(skills)

    for skill in skills:
        for q in QUESTION_BANK.get(skill, []):
            pool.append((skill, q))

    random.shuffle(pool)
    selected = pool[:question_count]

    # Fill remaining slots with general questions if the candidate's
    # recognized skills didn't yield enough bank questions.
    if len(selected) < question_count:
        remaining_general = [("general", q) for q in GENERAL_QUESTIONS]
        random.shuffle(remaining_general)
        needed = question_count - len(selected)
        selected.extend(remaining_general[:needed])

    questions = []
    for skill, (question, a, b, c, d, correct) in selected[:question_count]:
        questions.append({
            "question": question,
            "option_a": a, "option_b": b, "option_c": c, "option_d": d,
            "correct_answer": correct,
            "skill": skill,
        })
    return questions


def score_quiz(questions, submitted_answers):
    """
    questions: list of dicts (as returned by generate_quiz_questions, or DB rows)
    submitted_answers: dict {question_id_or_index(str): "A"/"B"/"C"/"D"}

    Returns (score_percent: float, correct_count: int, total: int)
    """
    total = len(questions)
    if total == 0:
        return 0.0, 0, 0
    correct = 0
    for idx, q in enumerate(questions):
        key = str(q.get("id", idx))
        given = submitted_answers.get(key)
        if given and given.upper() == q["correct_answer"].upper():
            correct += 1
    score = round((correct / total) * 100, 2)
    return score, correct, total
