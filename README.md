# WebVTT NLP 

This project is a tool to use NLP with Web Video Text Tracks Format (WebVTT) to batch process big Meeting Transcripts and automatically correct the transcripts using a LLM. 

## Overview

The main steps involved in the transcription correction process are:

1. **Parsing the Transcript**: The `parse_transcript` function reads the input WebVTT file and extracts the UUID, timestamp, and transcript lines.
2. **Saving to JSON**: The parsed data is saved to a JSON file using the `save_to_json` function.
3. **Preparing Messages for API Call**: The `prepare_messages` function formats the parsed data into messages suitable for an API call to a language model.
4. **Processing Data in Batches**: The `process_data` function processes the transcript data in batches, making API calls to correct the text.
5. **Updating JSON with Corrected Text**: The `parse_txt_and_update_json` function reads the corrected text from the API response and updates the JSON file with the corrected lines.
6. **Converting JSON to WebVTT**: The `convert_json_to_txt` function converts the corrected JSON data back into WebVTT format.

## Usage

1. **Convert Input to JSON**: Run the script to parse the input WebVTT file and save the data to `input.json`.
2. **Process Data**: The script processes the data in batches, making API calls to correct the transcript.
3. **Update JSON with Corrected Text**: The script updates the JSON file with the corrected text from the API response.
4. **Convert JSON to WebVTT**: The script converts the corrected JSON data back into WebVTT format and saves it to `output.txt`.

## Running the Script

Ensure you have a input.txt (with WebVTT contents) in the same folder as the main.py.

To run the script, execute the following command:
python main.py


