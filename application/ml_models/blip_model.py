from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

processor = BlipProcessor.from_pretrained(
    "Salesforce/blip-image-captioning-base",
    use_fast=False
)

model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)


def generate_caption(image):

    inputs = processor(
        images=image,
        return_tensors="pt"
    ).to(device)

    out = model.generate(
        **inputs,
        max_length=40,
        num_beams=5,
        repetition_penalty=1.2
    )

    caption = processor.decode(
        out[0],
        skip_special_tokens=True
    )

    return clean_caption(caption)


def clean_caption(text):

    text = text.strip().lower()

    remove_words = [
        "a photo of",
        "an image of",
        "this image shows",
        "a picture of"
    ]

    for w in remove_words:
        text = text.replace(w, "")

    return "Vehicle image shows: " + text.strip()