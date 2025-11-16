import json, numpy as np, joblib
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

print("Generating dummy model...")

# Feature list
features = ["opcode_balance","opcode_calls","opcode_storage","bytecode_length","complexity_score"]

# Generate fake training data
rng = np.random.default_rng(42)
X = rng.random((200, len(features)))
y = (0.6 * X[:,0] + 0.4 * X[:,1] + 0.2 * X[:,2] > 0.5).astype(int)

# Scale data
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train model
model = XGBClassifier(
    n_estimators=25,
    max_depth=4,
    learning_rate=0.3,
    subsample=0.9,
    colsample_bytree=0.9,
    reg_lambda=1.0,
    eval_metric="logloss",
)
model.fit(X_scaled, y)

# Create folder paths
Path("model").mkdir(parents=True, exist_ok=True)
Path("datasets").mkdir(parents=True, exist_ok=True)

# Save files
model.save_model("model/security_model.xgb")
joblib.dump(scaler, "model/scaler.pkl")
Path("datasets/feature_list.json").write_text(json.dumps(features, indent=2))

print("✔ Model, scaler, and feature list generated successfully!")
