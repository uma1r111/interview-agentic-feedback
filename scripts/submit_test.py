import json
import requests

API_URL = "http://127.0.0.1:8000/candidates"
FIXTURE_PATH = "fixtures/sample_candidate.json"

MOCK_MCQ_ANSWERS = {
    "q1_decision_trees": "A",
    "q2_regularization": "C",
    "q3_quantization": "B",
    "q4_rag_context": "D",
    "q5_activation_functions": "A"
}

def send_candidate_to_pipeline():
    print(f"Reading interview artifact file from '{FIXTURE_PATH}'...")
    try:
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            candidate_json_content = json.load(f)
            
        # Explicitly build the payload dictionary to match what IntakeRequestPayload expects
        payload = {
            "candidate_data": {
                "candidate_name": candidate_json_content.get("candidate_name"),
                "role_type": candidate_json_content.get("role_type"),
                "mcq_score": candidate_json_content.get("mcq_score", 0.0),
                "programming_answers": candidate_json_content.get("programming_answers", []),
                "session1_transcript": candidate_json_content.get("session1_transcript", ""),
                "session2_transcript": candidate_json_content.get("session2_transcript", "")
            },
            "mcq_selections": MOCK_MCQ_ANSWERS
        }
        
        print("Sending payload to LangGraph execution pool pipeline... (This invokes parallel AI agents)")
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 201:
            result = response.json()
            print("\n" + "="*60)
            print("🚀 SUCCESS: Multi-Agent evaluation completed cleanly!")
            print(f"Generated Candidate ID: {result['candidate_id']}")
            print("="*60)
            print("\nCopy the ID above, paste it into your Streamlit Sidebar, and click Load Profile.")
        else:
            print(f"\n❌ Pipeline stopped with status code {response.status_code}")
            print(f"Error Details: {response.text}")
            
    except FileNotFoundError:
        print(f"❌ Error: Could not locate fixture file at {FIXTURE_PATH}.")
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to FastAPI server. Ensure your Uvicorn window is up on port 8000.")

if __name__ == "__main__":
    send_candidate_to_pipeline()