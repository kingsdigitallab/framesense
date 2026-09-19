from ..answer_clips.operator import AnswerClips

class AnswerClipsVLM(AnswerClips):
    '''Let a VLM behind an openai-compatible API answer questions about a clip'''

    def _get_response_from_model(self, clip_path, collection_path):
        return self.send_prompt_to_openai_api_from_params(clip_path, collection_path)
