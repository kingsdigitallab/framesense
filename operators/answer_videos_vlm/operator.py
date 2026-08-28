from ..answer_videos.operator import AnswerVideos

class AnswerVideosVLM(AnswerVideos):
    '''Let a VLM behind an openai-compatible API answer questions about a video'''

    def _get_response_from_model(self, video_path, collection_path):
        return self.send_prompt_to_openai_api_from_params(video_path, collection_path)
