"""Tokenizer preparation without importing PyTorch or loading model weights."""
from pathlib import Path


class OfflineTokenizer:
    def __init__(self,path):
        from tokenizers import Tokenizer
        self.backend=Tokenizer.from_file(str(Path(path)))
        self.backend.no_truncation();self.backend.no_padding()

    def __call__(self,text,add_special_tokens=True,return_offsets_mapping=False,**kwargs):
        encoding=self.backend.encode(text,add_special_tokens=add_special_tokens)
        result={'input_ids':encoding.ids}
        if return_offsets_mapping:result['offset_mapping']=encoding.offsets
        return result
