"""
End-to-end API test for the full candidate evaluation pipeline.
Requires:
  - FastAPI server running: uvicorn api.main:app --reload
  - A real CV PDF file at the path below

Usage:
    python submit_test.py
    python submit_test.py <path_to_cv.pdf>   # override default PDF path
"""
import json
import sys
import requests

API_URL       = "http://127.0.0.1:8000/candidates"
FIXTURE_PATH  = "fixtures/sample_candidate.json"
DEFAULT_CV    = "fixtures/sample_cv.pdf"    # put any CV PDF here

MOCK_MCQ_ANSWERS = {
    "q1_decision_trees":       "A",
    "q2_regularization":       "C",
    "q3_quantization":         "B",
    "q4_rag_context":          "D",
    "q5_activation_functions": "A"
}


def send_candidate_to_pipeline(cv_pdf_path: str):
    print(f"\n{'='*60}")
    print("SUBMIT TEST — Full Pipeline API Test")
    print(f"{'='*60}")
    print(f"Reading fixture : {FIXTURE_PATH}")
    print(f"CV PDF file     : {cv_pdf_path}")

    # 1. Load the candidate fixture JSON
    try:
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            fixture = json.load(f)
    except FileNotFoundError:
        print(f"[Error] Fixture file not found: {FIXTURE_PATH}")
        sys.exit(1)

    # 2. Load the CV PDF as bytes
    try:
        with open(cv_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        print(f"CV file size    : {len(pdf_bytes):,} bytes")
    except FileNotFoundError:
        print(f"[Error] CV PDF not found: {cv_pdf_path}")
        print("  Tip: put any CV PDF at fixtures/sample_cv.pdf")
        print("       or pass a path: python submit_test.py C:/path/to/cv.pdf")
        sys.exit(1)

    # 3. Build the multipart/form-data request
    # Each field is a Form() param on the API — no JSON body anymore.
    # mcq_selections must be sent as a JSON string inside the form.
    form_data = {
        "candidate_name":       fixture["candidate_name"],
        "role_type":            fixture["role_type"],
        "mcq_score":            str(fixture["mcq_score"]),
        "programming_answer_1": fixture["programming_answers"][0],
        "programming_answer_2": fixture["programming_answers"][1],
        "session1_transcript":  fixture["session1_transcript"],
        "session2_transcript":  fixture["session2_transcript"],
        "mcq_selections":       json.dumps(MOCK_MCQ_ANSWERS),  # JSON string in form field
    }

    files = {
        "cv_file": ("cv.pdf", pdf_bytes, "application/pdf")
    }

    # 4. Send the request
    print("\nSending multipart request to pipeline... (parallel AI agents running)\n")
    try:
        response = requests.post(API_URL, data=form_data, files=files)
    except requests.exceptions.ConnectionError:
        print("[Error] Cannot connect to FastAPI server.")
        print("   Start it first: uvicorn api.main:app --reload")
        sys.exit(1)

    # 5. Handle response
    if response.status_code == 201:
        result = response.json()
        print("=" * 60)
        print("SUCCESS: Multi-agent evaluation completed!")
        print(f"   Candidate ID : {result['candidate_id']}")
        print(f"   Status       : {result['status']}")
        print("=" * 60)
        print("\nNext steps:")
        print(f"  • Fetch report : GET http://127.0.0.1:8000/candidates/{result['candidate_id']}/report")
        print(f"  • Dashboard    : paste the ID into the Streamlit sidebar")
    else:
        print(f"[Error] Pipeline returned status {response.status_code}")
        try:
            print(f"   Error: {response.json().get('detail', response.text)}")
        except Exception:
            print(f"   Raw response: {response.text}")


if __name__ == "__main__":
    cv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CV
    send_candidate_to_pipeline(cv_path)