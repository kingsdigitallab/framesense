from ..answer_videos.operator import AnswerVideos

class AnswerVideosQwen3VL(AnswerVideos):
    '''Let a Qwen3-VL model answer questions about a video'''

    def _get_response_from_model(self, video_path, collection_path):
        return self._call_service_processor(video_path, collection_path)
