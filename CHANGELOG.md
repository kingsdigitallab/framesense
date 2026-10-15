# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Each change is tagged as [major] or [minor].

## v1.1.0

### Added

- [major] **run_pipeline**: new operator running a series of operators in sequence,
  as defined under meta.pipelines in the collections file, with support for skip (-k)
  and a stop_before param and operation property to stop the pipeline before a given operation.
- [major] **detect_speech_vad**: new operator detecting voice segments in clip sound files with silero-vad.
- [major] **transcription_vad_sub**: new operator writing clip transcriptions into srt files
  filtered by the voice segments, with optional splitting of long segments into cue-sized pieces,
  re-filtering of stale srts and dropping of short-overlap and hallucinated cues.
- [major] **sub_clips_ffmpeg**: new operator burning subtitles onto clips,
  with outline and shadow for legibility on bright backgrounds,
  near-lossless fast x264 re-encoding defaults and symlinks for the clips with an empty srt file.
- [major] **separate_clips_ffmpeg**: new operator splitting clips around programme separators
  into -prog clips, with a smart cut mode producing second-accurate near-lossless clips in a single re-encode.
- [major] **answer_separators_vlm**: new operator listing the separators between distinct programmes in a video,
  with clip chunks cached under _chunks (cache_chunks param, off by default)
  and processing issues and invalid answers recorded in the output under stats.chunks.
- [major] **clip_full_video**: new operator creating a clip covering the whole video by symlinking it,
  tagged with -full.
- [minor] **extract_sound_ffmpeg**, **transcribe_speech_parakeet** and **clip_full_video**:
  support for skip (-k) and end-of-run summaries.
- [minor] **clip_full_video**: skips ffprobe entirely when a full clip folder already exists,
  and reports the missing items.
- [minor] **base**: the -f filter argument accepts multiple values separated by |,
  and named filters defined under the filters attribute of a collection.
- [minor] **base**: the -e exclude argument skips the paths matching keywords,
  usable from the command line and from pipeline operations.
- [minor] **base**: all operators ignore the paths with a component starting with _.
- [minor] **base**: new params for prompting with videos: video_tokens, max_fps,
  the video media type and filter_questions, to only submit specific questions to a VLM.
- [minor] **base**: the duration of any request to an LLM is now recorded.
- [minor] **base**: LLM answers made of paragraphs ending with a json block
  are parsed by _parse_dirty_json, with unit tests.

### Changed

- [major] **answer_clips**: **Breaking** — answers questions about clips, not videos,
  with a clip_answers.json file alongside each clip;
  the answer_videos* operators are renamed to answer_clips*.
- [major] **answer_clips**: answer_videos is now a pure abstract class:
  its logic lives in **answer_clips_qwen3vl** (qwen 3 vl)
  and **answer_clips_vlm** (thinking, video and other params),
  and more operators use the shared send_prompt_to_openai_api_from_params.
- [major] **sub_clips_ffmpeg**: **Breaking** — burns the srt file produced
  by **transcription_vad_sub** instead of converting transcription.json.

### Fixed

- [minor] **extract_sound_ffmpeg**: now works with symlinked full clips.
- [minor] **answer_clips_vlm**: the params of VLM requests are now sent properly to inference engines,
  with fps and max_frames moved to media_io_kwargs so vllm can read them.
- [minor] **base**: a relative path to the video is now used for the VLM requests to llama-server.
- [minor] **answer_clips**: the max_new_tokens param is renamed into max_tokens.
- [minor] **answer_clips**: an empty filter_questions no longer filters out any question.
- [minor] **answer_clips**: used strip instead of trim on strings (trim is not a Python method).
- [minor] **answer_separators_vlm**: no longer crashes due to non-numeric usage data aggregation.
- [minor] **answer_separators_vlm**: the missing payload metadata is added to the response,
  and the chunks metadata is moved to stats.
- [minor] **base** and **answer_separators_vlm**: fixed nested quotation marks in strings.
- [minor] **base**: send_prompt_to_openai_api_from_params better handles truncated responses,
  max_new_tokens and context_length.
- [minor] **base**: _parse_dirty_json falls back to the trailing-json parser
  when the whole answer only looks like a single json block.
- [minor] **sub_clips_ffmpeg**: subtitles are burned into a temporary file renamed on completion,
  to make the operation atomic.
- [minor] **separate_clips_ffmpeg**: no longer reads the separators of the filtered out clips.
- [minor] **clip_full_video**: uses the framesense log instead of print.
- [minor] **annotations**: uses the correct log function, with the right paths to annotations files.
- [minor] **base** and **answer_frames_vlm**: Python 3.11 compatibility,
  using different quote types inside f-string expressions.
- [minor] **ci**: the codemeta-to-citation-cff workflow was using deprecated actions.
