import torch
import tiktoken
import torch.nn.functional as F
from gpt2 import GPT, GPTConfig
import argparse

def load_model(model_file):
    print("Loading model...")
    ## Load the model
    checkpoint = torch.load(model_file)
    weights = checkpoint['model']

    # Init the model
    model = GPT(GPTConfig(vocab_size=50257))
    model.load_state_dict(weights)

    # Move the model to GPU
    model.to(device)
    return model

## Generator Function to generate from the model
def streaming_generate(model, prompt):
    enc = tiktoken.get_encoding("gpt2")
    model.eval()
    max_length = 500
    tokens = enc.encode(prompt)
    tokens = torch.tensor([tokens], dtype=torch.long)
    xgen = tokens.to(device)
    sample_rng = torch.Generator(device=device)
    sample_rng.manual_seed(42)

    while xgen.size(1) < max_length:
        # forward the model to get the logits
        with torch.no_grad():
            logits, loss = model(xgen) # (B, T, vocab_size)
            # take the logits at the last position
            logits = logits[:, -1, :] # (B, vocab_size)
            # get the probabilities
            probs = F.softmax(logits, dim=-1)
            # do top-k sampling of 50 (huggingface pipeline default)
            # topk_probs here becomes (5, 50), topk_indices is (5, 50)
            topk_probs, topk_indices = torch.topk(probs, 50, dim=-1)
            # select a token from the top-k probabilities
            # note: multinomial does not demand the input to sum to 1
            ix = torch.multinomial(topk_probs, 1, generator=sample_rng) # (B, 1)
            # gather the corresponding indices
            xcol = torch.gather(topk_indices, -1, ix) # (B, 1)

            # Check if we reached end of generation
            val = xcol.tolist()[0]
            decoded = enc.decode(val)
            if decoded == "<|endoftext|>":
                break
            else:
                yield decoded

            # append to the sequence
            xgen = torch.cat((xgen, xcol), dim=1)
    

def preprocess_function(example):
    text = f"### Instruction:\n{example['instruction']}\n\n### Input:\n{example['input']}\n\n### Response:\n{example['output']}"
    return text


args = argparse.ArgumentParser()
args.add_argument("--model_file", type=str, required=True)
args = args.parse_args()

# Set Device
device = "cuda:0"
model = load_model(args.model_file)

while True:
    try:
        inp = input("Enter a prompt: ")
        if not inp:
            continue

        ## Generate from the Model
        prompt = preprocess_function({"instruction": inp, "input": "", "output": ""})
        for tok in streaming_generate(model, prompt):
            print(tok, end='')
        print()
    except KeyboardInterrupt:
        print("Bye!")
        break
