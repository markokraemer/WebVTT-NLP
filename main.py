import json
import asyncio
from api_call_util import make_llm_api_call
import os
import json
import re
import shutil
import aiofiles
import streamlit as st

# Ensure the 'temp' directory exists
if not os.path.exists('temp'):
    os.makedirs('temp')

### PRE

def parse_transcript(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    data = []
    entry = {}
    for line in lines:
        uuid_match = re.match(r'^(\w{8}-\w{4}-\w{4}-\w{4}-\w{12}-\d+)', line)
        timestamp_match = re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', line)
        
        if uuid_match:
            if entry:
                data.append(entry)
                entry = {}
            entry['UUID'] = uuid_match.group(1)
        elif timestamp_match:
            entry['Timestamp'] = timestamp_match.group(0)
        else:
            content_line = line.strip()
            if content_line:
                if 'Line1' not in entry:
                    entry['Line1'] = content_line
                else:
                    entry['Line2'] = content_line

    # Append the last entry if not empty
    if entry:
        data.append(entry)

    return data

def save_to_json(data, output_file):
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def convert_input_to_json(file_path='input.txt'):
    transcript_data = parse_transcript(f'{file_path}')
    # Ensure the file is created to avoid FileNotFoundError
    if not os.path.exists('temp/input.json'):
        with open('temp/input.json', 'w', encoding='utf-8') as file:
            json.dump([], file, indent=4, ensure_ascii=False)
    
    save_to_json(transcript_data, 'temp/input.json')

### PROCESS


# Parse the data based on curly brackets
def parse_data(data):
    blocks = []
    current_block = ""
    inside_block = False
    for char in data:
        if char == '{':
            inside_block = True
            current_block = char
        elif char == '}':
            current_block += char
            inside_block = False
            blocks.append(current_block)
        elif inside_block:
            current_block += char
    return blocks

# Prepare messages for the API call
def prepare_messages(data, system_message):
    messages = [
        {
            "role": "system",
            "content": f"{system_message}"
        },
        {
            "role": "user",
            "content": json.dumps(data)
        }
    ]
    return messages

# Process the data in batches
async def process_data(system_message):
    # Load input data
    async with aiofiles.open('temp/input.json', 'r') as infile:
        input_data = await infile.read()
    # Load the working copy data
    async with aiofiles.open('temp/input.json', 'r') as wipfile:
        wip_data = await wipfile.read()
            
    wip_blocks = parse_data(wip_data)
    batch_size = 20

    async def process_batch(batch, batch_index, system_message):
        messages = prepare_messages(batch, system_message)
        response = await make_llm_api_call(messages, "gpt-4o", max_tokens=4096, temperature=0.4)
        response_content = response.choices[0].message['content']
        print(f"Batch {batch_index + 1} response content: {response_content}")

        # Save the raw response content to a file
        async with aiofiles.open(f'temp/wip-output-batch-{batch_index + 1}.txt', 'w') as outfile:
            await outfile.write(response_content)

    tasks = []
    for i in range(0, len(wip_blocks), batch_size):
        batch = wip_blocks[i:i+batch_size]
        tasks.append(process_batch(batch, i//batch_size, system_message))

    await asyncio.gather(*tasks)

    # Combine all batch files into a single file
    combined_content = ""
    for batch_index in range((len(wip_blocks) + batch_size - 1) // batch_size):
        async with aiofiles.open(f'temp/wip-output-batch-{batch_index + 1}.txt', 'r') as batch_file:
            combined_content += await batch_file.read()

    async with aiofiles.open('temp/wip-output-combined.txt', 'w') as combined_file:
        await combined_file.write(combined_content)

### FINAL

def parse_txt_and_update_json(txt_file_path, input_json_path, output_json_path):
    # Read the contents of the .txt file
    with open(txt_file_path, 'r', encoding='utf-8') as txt_file:
        txt_content = txt_file.read()
    print(f"Read txt file: {txt_file_path}")

    # Find all contents within curly brackets
    pattern = re.compile(r'\{(.*?)\}', re.DOTALL)
    matches = pattern.findall(txt_content)
    print(f"Found matches: {matches}")

    # Read the input JSON file
    with open(input_json_path, 'r', encoding='utf-8') as json_file:
        json_data = json.load(json_file)
    print(f"Loaded JSON data from: {input_json_path}")

    # Update the JSON data with the new corrected lines for each UUID found
    for match in matches:
        try:
            item = json.loads("{" + match + "}")
            uuid = item.get("UUID")
            corrected_line1 = item.get("CorrectedLine1", "").strip()
            corrected_line2 = item.get("CorrectedLine2", "").strip()
            print(f"Processing item: {item}")

            found = False
            for json_item in json_data:
                if json_item.get("UUID") == uuid:
                    json_item["CorrectedLine1"] = corrected_line1
                    if corrected_line2:
                        json_item["CorrectedLine2"] = corrected_line2
                    print(f"Updated JSON item: {json_item}")
                    found = True
                    break

            if not found:
                print(f"Error: UUID {uuid} not found in JSON data.")

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for match: {match}\nError: {e}")
            continue

    # Write the updated JSON data to the output file
    with open(output_json_path, 'w', encoding='utf-8') as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=4)
    print(f"Updated JSON data written to: {output_json_path}")

def process_all_files_in_current_dir():
    current_dir = os.getcwd()
    print(current_dir)
    txt_file_path = os.path.join(current_dir, 'temp/wip-output-combined.txt')
    input_json_path = os.path.join(current_dir, 'temp/input.json')
    output_json_path = os.path.join(current_dir, 'temp/output.json')

    # Copy input.json to output.json
    shutil.copy(input_json_path, output_json_path)

    # Parse the .txt file and update the output.json
    parse_txt_and_update_json(txt_file_path, input_json_path, output_json_path)

def convert_json_to_txt(json_path, txt_path):
    with open(json_path, 'r', encoding='utf-8') as json_file:
        json_data = json.load(json_file)

    with open(txt_path, 'w', encoding='utf-8') as txt_file:
        txt_file.write("WEBVTT\n\n")
        for item in json_data:
            if "UUID" in item and "Timestamp" in item:
                txt_file.write(f"{item['UUID']}\n")
                txt_file.write(f"{item['Timestamp']}\n")
                if "CorrectedLine1" in item:
                    txt_file.write(f"{item['CorrectedLine1']}\n")
                elif "Line1" in item:
                    txt_file.write(f"{item['Line1']}\n")
                if "CorrectedLine2" in item:
                    txt_file.write(f"{item['CorrectedLine2']}\n")
                elif "Line2" in item:
                    txt_file.write(f"{item['Line2']}\n")
                txt_file.write("\n")

# Streamlit UI
st.title("Transcript Correction")

uploaded_file = st.file_uploader("Upload input.txt", type="txt")
system_message = st.text_area("System Message", value=""" You are an expert proofreader and corrector specializing in correcting machine-generated transcripts.
Your main objective is correcting German text to be semantically and grammatically accurate so that the sentences make sense. Ensure that you only fix the machine-translated content and keep the UUID and timestamp unchanged to allow us to reload it into our system. 
""")
system_message += """
You will receive a JSON with multiple objects, each containing an UUID, Timestamp, Line 1 & Line 2 (if applicable). You have to correct Line 1 & Line 2 (if applicable) and return a JSON containing all of the Objects corrected with its respective UUID, CorrectedLine1, CorrectedLine2 (if applicable). Output in JSON Format. 

<example_input>
{
    "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-0",
    "Timestamp": "00:00:02.280 --> 00:00:06.430",
    "Line1": "Wartet Datenschutzabfrage steht",
    "Line2": "jetzt im Chatbereich und ich",
},
{
    "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-1",
    "Timestamp": "00:00:06.430 --> 00:00:10.648",
    "Line1": "bitte euch im Chatbereich darauf",
    "Line2": "zu antworten, ob ihr mit der",
},
{
    "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-2",
    "Timestamp": "00:00:10.648 --> 00:00:14.527",
    "Line1": "Aufnahme einverstanden seid",
    "Line2": "beziehungsweise keine Daumen",
},
{
    "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-3",
    "Timestamp": "00:00:14.527 --> 00:00:16.160",
    "Line1": "hoch. Bitte schriftlich.",
},
{
    "UUID": "db7b7615-3c6e-491a-97fc-e96b469dd9f7-0",
    "Timestamp": "00:00:16.990 --> 00:00:18.670",
    "Line1": "Reinsetzen, weil dann ist der",
    "Line2": "Name dabei.",
},
</example_input>

<example_output>
{
    "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-0",
    "CorrectedLine1": "Wartet, die Datenschutzabfrage steht",
    "CorrectedLine2": "jetzt im Chatbereich und ich"
},
{
    "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-1",
    "CorrectedLine1": "Ich bitte euch, im Chatbereich darauf",
    "CorrectedLine2": "zu antworten, ob ihr mit der"
},
{
    "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-2",
    "CorrectedLine1": "Aufnahme einverstanden seid",
    "CorrectedLine2": "beziehungsweise keine Daumen"
},
{
    "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-3",
    "Line1": "hoch. Bitte schriftlich.",
    "CorrectedLine1": "hoch. Bitte schriftlich."
},
{
    "UUID": "db7b7615-3c6e-491a-97fc-e96b469dd9f7-0",
    "CorrectedLine1": "Reinsetzen, weil dann ist der",
    "CorrectedLine2": "Name dabei."
},
</example_output>

OUTPUT EVERYTHING NOT JUST 1! ALL OF THEM. EVERY OBJECT.               

YOU ARE AN EXPERT. BE PERFECT.
"""

if st.button("Process"):
    if uploaded_file is not None:
        with open("temp/input.txt", "wb") as f:
            f.write(uploaded_file.getbuffer())
        convert_input_to_json("temp/input.txt")
        asyncio.run(process_data(system_message))
        process_all_files_in_current_dir()
        convert_json_to_txt("temp/output.json", "temp/output.txt")
        st.success("Processing complete. You can now download the output file.")

        with open("temp/output.txt", "rb") as f:
            st.download_button("Download output.txt", f, file_name="output.txt")


# if __name__ == "__main__":
#     convert_input_to_json()

#     system_message = """ You are an expert proofreader and corrector specializing in correcting machine-generated transcripts.
# Your main objective is correcting German text to be semantically and grammatically accurate so that the sentences make sense. Ensure that you only fix the machine-translated content and keep the UUID and timestamp unchanged to allow us to reload it into our system. 

# You will receive a JSON with multiple objects, each containing an UUID, Timestamp, Line 1 & Line 2 (if applicable). You have to correct Line 1 & Line 2 (if applicable) and return a JSON containing all of the Objects corrected with its respective UUID, CorrectedLine1, CorrectedLine2 (if applicable). Output in JSON Format. 
 
# <example_input>
# {
#     "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-0",
#     "Timestamp": "00:00:02.280 --> 00:00:06.430",
#     "Line1": "Wartet Datenschutzabfrage steht",
#     "Line2": "jetzt im Chatbereich und ich",
#   },
#   {
#     "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-1",
#     "Timestamp": "00:00:06.430 --> 00:00:10.648",
#     "Line1": "bitte euch im Chatbereich darauf",
#     "Line2": "zu antworten, ob ihr mit der",
#   },
#   {
#     "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-2",
#     "Timestamp": "00:00:10.648 --> 00:00:14.527",
#     "Line1": "Aufnahme einverstanden seid",
#     "Line2": "beziehungsweise keine Daumen",
#   },
#   {
#     "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-3",
#     "Timestamp": "00:00:14.527 --> 00:00:16.160",
#     "Line1": "hoch. Bitte schriftlich.",
#   },
#   {
#     "UUID": "db7b7615-3c6e-491a-97fc-e96b469dd9f7-0",
#     "Timestamp": "00:00:16.990 --> 00:00:18.670",
#     "Line1": "Reinsetzen, weil dann ist der",
#     "Line2": "Name dabei.",
#   },
#   </example_input>

#   <example_output>
# {
#     "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-0",
#     "CorrectedLine1": "Wartet, die Datenschutzabfrage steht",
#     "CorrectedLine2": "jetzt im Chatbereich und ich"
#   },
#   {
#     "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-1",
#     "CorrectedLine1": "Ich bitte euch, im Chatbereich darauf",
#     "CorrectedLine2": "zu antworten, ob ihr mit der"
#   },
#   {
#     "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-2",
#     "CorrectedLine1": "Aufnahme einverstanden seid",
#     "CorrectedLine2": "beziehungsweise keine Daumen"
#   },
#   {
#     "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-3",
#     "Line1": "hoch. Bitte schriftlich.",
#     "CorrectedLine1": "hoch. Bitte schriftlich."
#   },
#   {
#     "UUID": "db7b7615-3c6e-491a-97fc-e96b469dd9f7-0",
#     "CorrectedLine1": "Reinsetzen, weil dann ist der",
#     "CorrectedLine2": "Name dabei."
#   },
# </example_output>

# OUTPUT EVERYTHING NOT JUST 1! ALL OF THEM. EVERY OBJECT.               

# YOU ARE AN EXPERT. BE PERFECT.

# """
   
#     translator_system_message=""" You are an expert translator specializing in translating German text to English.
#     Your main objective is to ensure that the translations are semantically and grammatically accurate so that the sentences make sense. Ensure that you only translate the content and keep the UUID and timestamp unchanged to allow us to reload it into our system.

#     You will receive a JSON with multiple objects, each containing a UUID, Timestamp, Line 1, and Line 2 (if applicable). You have to translate Line 1 and Line 2 (if applicable) and return a JSON containing all of the objects translated with their respective UUID, CorrectedLine1, CorrectedLine2 (if applicable). Output in JSON Format.

#     <example_input>
#     {
#         "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-0",
#         "Timestamp": "00:00:02.280 --> 00:00:06.430",
#         "Line1": "Wartet Datenschutzabfrage steht",
#         "Line2": "jetzt im Chatbereich und ich",
#     },
#     {
#         "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-1",
#         "Timestamp": "00:00:06.430 --> 00:00:10.648",
#         "Line1": "bitte euch im Chatbereich darauf",
#         "Line2": "zu antworten, ob ihr mit der",
#     },
#     {
#         "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-2",
#         "Timestamp": "00:00:10.648 --> 00:00:14.527",
#         "Line1": "Aufnahme einverstanden seid",
#         "Line2": "beziehungsweise keine Daumen",
#     },
#     {
#         "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-3",
#         "Timestamp": "00:00:14.527 --> 00:00:16.160",
#         "Line1": "hoch. Bitte schriftlich.",
#     },
#     {
#         "UUID": "db7b7615-3c6e-491a-97fc-e96b469dd9f7-0",
#         "Timestamp": "00:00:16.990 --> 00:00:18.670",
#         "Line1": "Reinsetzen, weil dann ist der",
#         "Line2": "Name dabei.",
#     },
#     </example_input>

#     <example_output>
#     {
#         "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-0",
#         "CorrectedLine1": "Wait, the data protection query is",
#         "CorrectedLine2": "now in the chat area and I",
#     },
#     {
#         "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-1",
#         "CorrectedLine1": "ask you to respond in the chat area",
#         "CorrectedLine2": "about whether you agree to the",
#     },
#     {
#         "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-2",
#         "CorrectedLine1": "recording or not give a thumbs",
#         "CorrectedLine2": "up. Please in writing.",
#     },
#     {
#         "UUID": "9aad3f5c-a5e7-40b2-bd76-4eba2aa0d70a-3",
#         "CorrectedLine1": "up. Please in writing.",
#     },
#     {
#         "UUID": "db7b7615-3c6e-491a-97fc-e96b469dd9f7-0",
#         "CorrectedLine1": "Insert it in because then the",
#         "CorrectedLine2": "name is included.",
#     },
#     </example_output>

#     OUTPUT EVERYTHING NOT JUST 1! ALL OF THEM. EVERY OBJECT.

#     YOU ARE AN EXPERT. BE PERFECT.
#     """
   
#     asyncio.run(process_data(system_message))

#     process_all_files_in_current_dir()
#     convert_json_to_txt("temp/output.json", "output.txt")


