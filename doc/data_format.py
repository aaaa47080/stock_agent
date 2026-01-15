# 洗腎衛教資料庫範例
import requests
API_BASE = "http://172.23.37.2:8100"

#洗腎資料＋表格＋圖片
def Run_LLM(llm, question, json_data,llm_info, SystemPrompt = content):
    # print(llm, question, json_data, SystemPrompt)
    # prompt = make_conversation(question, json_data, SystemPrompt)
    # output = llm(
    #     prompt, # Prompt
    #     max_tokens=llm_info['max_tokens'],
    #     temperature = llm_info['temperature'],
    #     top_k = llm_info['top_k'],
    #     top_p = llm_info['top_p'], # Generate up to 32 tokens, set to None to generate up to the end of the context window
    #     stop=["<|eot_id|>", "Human:", "human:", "Instructions:"], # Stop generating just before the model would generate a new question
    #     echo=False # Echo the prompt back in the output
    # ) # Generate a completion, can also call create_completion
    # print(output)
    # result = output['choices'][0]['text']
    # result = re.sub(r'^assistant\n*', '', result)
    result = requests.post(f"{API_BASE}/chat", json={
        "user_id": "user_001",
        "message": question,
        "session_id": "session_001",
        "enable_short_term_memory": False,
        "datasource_ids": ["dialysis_education"]
    })
    return result


#感染資料科文字＋圖片＋表格
def Run_LLM(llm, question, json_data,llm_info, SystemPrompt = content):
    # print(llm, question, json_data, SystemPrompt)
    # prompt = make_conversation(question, json_data, SystemPrompt)
    # output = llm(
    #     prompt, # Prompt
    #     max_tokens=llm_info['max_tokens'],
    #     temperature = llm_info['temperature'],
    #     top_k = llm_info['top_k'],
    #     top_p = llm_info['top_p'], # Generate up to 32 tokens, set to None to generate up to the end of the context window
    #     stop=["<|eot_id|>", "Human:", "human:", "Instructions:"], # Stop generating just before the model would generate a new question
    #     echo=False # Echo the prompt back in the output
    # ) # Generate a completion, can also call create_completion
    # print(output)
    # result = output['choices'][0]['text']
    # result = re.sub(r'^assistant\n*', '', result)
    result = requests.post(f"{API_BASE}/chat", json={
        "user_id": "user_001",
        "message": question,
        "session_id": "session_001",
        "enable_short_term_memory": False,
        "datasource_ids": ["medical_kb_jsonl", "educational_images"]
    })
    return result

#公共衛教資料＋圖片＋表格
def Run_LLM(llm, question, json_data,llm_info, SystemPrompt = content):
    # print(llm, question, json_data, SystemPrompt)
    # prompt = make_conversation(question, json_data, SystemPrompt)
    # output = llm(
    #     prompt, # Prompt
    #     max_tokens=llm_info['max_tokens'],
    #     temperature = llm_info['temperature'],
    #     top_k = llm_info['top_k'],
    #     top_p = llm_info['top_p'], # Generate up to 32 tokens, set to None to generate up to the end of the context window
    #     stop=["<|eot_id|>", "Human:", "human:", "Instructions:"], # Stop generating just before the model would generate a new question
    #     echo=False # Echo the prompt back in the output
    # ) # Generate a completion, can also call create_completion
    # print(output)
    # result = output['choices'][0]['text']
    # result = re.sub(r'^assistant\n*', '', result)
    result = requests.post(f"{API_BASE}/chat", json={
        "user_id": "user_001",
        "message": question,
        "session_id": "session_001",
        "enable_short_term_memory": False,
        "datasource_ids": ["public_health", "educational_images"]
    })
    return result
