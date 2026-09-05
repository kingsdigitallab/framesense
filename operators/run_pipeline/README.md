# run_pipeline

## Input

* a pipeline defined in the collections file under meta.pipelines

## Output

* the outputs of each operator in the pipeline

## Method

Run a series of operators in sequence,
as defined in the pipeline P of the collections file:

```json
{
    "meta": {
        "pipelines": {
            "P": {
                "operations": [
                    {
                        "operator": "make_clips_ffmpeg",
                        "params": {}
                    },
                    {
                        "operator": "make_shots_scenedetect",
                        "params": {
                            "threshold": 27
                        }
                    }
                ]
            }
        }
    }
}
```

Each operation runs its operator
with the same behaviour as if it was run
from the command line.

The params of an operation supersede
the collections-level params (meta.params),
but never the environment variables.

The whole pipeline is validated
before the first operation is run.

The pipeline stops at the first operation which fails.

The -f and -v arguments are passed to every operation.
The -f argument is ignored, with a warning,
by the operators which don't support it.

The -r and -k arguments are not supported by run_pipeline.
To redo an operation, run its operator directly.

## Parameters

* pipeline: name of the pipeline to run, as defined under meta.pipelines in the collections file. Default: default

## Run if

Always runs.
Each operator in the pipeline skips
the inputs which output already exists (as usual).
