from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

processor = None
model = None


def load_blip():
    global processor, model

    if processor is None:
        processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        )

        model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        )

        model.eval()

    return processor, model



def generate_caption(image):

    processor, model = load_blip()

    inputs = processor(
        images=image,
        return_tensors="pt"
    )

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=20
        )

    caption = processor.decode(
        output[0],
        skip_special_tokens=True
    )

    return caption