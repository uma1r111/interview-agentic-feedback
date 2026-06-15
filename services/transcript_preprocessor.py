import re
import logging

logger = logging.getLogger(__name__)

class TranscriptPreprocessor:
    """
    Strips raw diarized transcripts (with timestamps and speaker labels) into clean 
    Q&A paired formats. This reduces noise for evaluation LLMs and prevents 
    timestamp/speaker pollution in extracted evidence quotes.
    """
    def __init__(self):
        # Matches [HH:MM:SS] SpeakerName: Content
        self.line_pattern = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s+([^:]+):\s+(.*)$")

    def process(self, raw_transcript: str) -> str:
        """
        Takes a raw transcript and returns a formatted Q&A string.
        Contiguous interviewer turns are merged into a single 'Q' block.
        Contiguous candidate turns are merged into a single 'A' block.
        """
        if not raw_transcript:
            return ""

        lines = raw_transcript.split('\n')
        
        qa_pairs = []
        current_speaker_type = None  # "Q" or "A"
        current_block = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            match = self.line_pattern.match(line)
            if match:
                speaker, content = match.groups()
                speaker_lower = speaker.lower()
                
                # Determine speaker type
                if "interviewer" in speaker_lower:
                    new_type = "Q"
                elif "candidate" in speaker_lower:
                    new_type = "A"
                else:
                    # Fallback for unknown labels
                    new_type = "UNKNOWN"
                
                # If speaker type changes (e.g. from interviewer to candidate)
                if current_speaker_type != new_type:
                    # Save the previous block
                    if current_speaker_type and current_block:
                        qa_pairs.append(f"{current_speaker_type}: {' '.join(current_block)}")
                    
                    current_speaker_type = new_type
                    current_block = [content]
                else:
                    # Same speaker type (e.g., two interviewers back-to-back, or continuous candidate)
                    current_block.append(content)
            else:
                # Continuation of the previous line if it doesn't have a timestamp
                if current_block:
                    current_block.append(line)
                else:
                    # Text before any speaker is identified — ignore or append as context
                    pass

        # Append the final block
        if current_speaker_type and current_block:
            qa_pairs.append(f"{current_speaker_type}: {' '.join(current_block)}")

        return "\n\n".join(qa_pairs)
