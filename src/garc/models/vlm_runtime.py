from pathlib import Path
import os
import time
import torch

def load_vlm(model_path=None):
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    path = str(Path(model_path or os.environ["GARC_VLM_MODEL"]).expanduser())
    model = Qwen3VLForConditionalGeneration.from_pretrained(path, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
    processor = AutoProcessor.from_pretrained(path, trust_remote_code=True)
    model.eval()
    return model, processor, path

def confirm_image(model, processor, image, prompt, max_new_tokens=256):
    from PIL import Image
    if not isinstance(image, Image.Image): image = Image.fromarray(image)
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[image], padding=True, return_tensors="pt").to(model.device)
    if torch.cuda.is_available(): torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.inference_mode(): output = model.generate(**inputs, do_sample=False, max_new_tokens=max_new_tokens)
    if torch.cuda.is_available(): torch.cuda.synchronize()
    raw = processor.batch_decode(output[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
    return raw, {"latency_sec": time.perf_counter() - t0}
