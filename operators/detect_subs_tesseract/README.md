# detect_subs_tesseract

## Input

* a clip file

## Output

* `hard_sub_segments.json` alongside each clip: the list of the periods of the clip
  during which burned-in subtitles are visible, each with its start and end timecodes
  in seconds, relative to the clip. The format matches `voice_segments.json`, so that
  another operator can filter cues against it (e.g. skip the cues overlapping a period
  where subtitles are already burned in the image).
* the sample images in a `_subs_samples/` folder next to the clip file,
  removed once the clip has been processed, unless `cache_samples` is true
  (e.g. to inspect what the OCR reads).

## Method

The bottom band of the clip (the last `band_height` fraction of its height, 25%
by default), where subtitles usually sit, is sampled every `sample_interval_secs`
seconds (2 by default) with a single FFMPEG pass, deinterlaced when `deinterlace`
is enabled (on by default, broadcast video being usually interlaced). Each sample
is a small grayscale image, 640px wide.

All the samples are OCR-ed with a single call to tesseract, in the `ocr_lang`
language (English by default). A sample is positive when its OCR text holds at
least 2 characters.

The positive samples are grouped into runs, consecutive samples being allowed to
lie `gap_tolerance_secs` seconds apart (6 by default, i.e. up to two missed samples
at the default interval): an OCR miss on a blurry or transitional frame does not
break a period.

Each run becomes a subtitle segment: its boundaries are the times of its first and
last samples, padded by one sample interval so that the subtitles appearing between
two samples are covered, and clamped to the start and the end of the clip. Runs
shorter than `min_segment_secs` are dropped (one-off captions, location slates), so
are the runs holding fewer than `min_distinct_texts` distinct OCR texts (2 by
default): subtitles change from cue to cue, whereas static overlays such as station
logos, tickers and name straps do not.

No assumption is made about the homogeneity of the clip: a 90-minute tape mixing
subtitled and unsubtitled programmes yields the periods of the subtitled ones only.
The boundaries of a period are accurate within one sample interval.

The duration of the clip is read from its name, per the framesense convention
(e.g. `00.00.00-6582-full.mp4` covers the first 6582 seconds of its video).

Note: texts are normalized with latin alphanumeric characters only, non-latin
scripts are not supported yet.

## Parameters

* `sample_interval_secs`: seconds between two samples, the period boundaries are accurate within this amount (default: 2)
* `band_height`: fraction of the frame height sampled from the bottom (default: 0.25)
* `deinterlace`: deinterlace the samples with yadif (default: 1)
* `gap_tolerance_secs`: largest gap between the positive samples of a same period (default: 6)
* `min_segment_secs`: shortest subtitle period kept (default: 5)
* `min_distinct_texts`: fewest distinct OCR texts within a period for it to be subtitles (default: 2)
* `ocr_lang`: language of the tesseract OCR model (default: eng)
* `cache_samples`: keep the samples on disk after processing (default: 0)

## Run if

The `hard_sub_segments.json` file of the clip does not already exist.

## Redo (-r)

Supported. The samples are extracted and OCR-ed again.

## Filtering (-f)

Supported.
