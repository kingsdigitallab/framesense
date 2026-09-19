from ..answer_clips.operator import AnswerClips

class AnswerClipsQwen3VL(AnswerClips):
    '''Let a Qwen3-VL model answer questions about a clip'''

    def _get_response_from_model(self, clip_path, collection_path):
        return self._call_service_processor(clip_path, collection_path)
