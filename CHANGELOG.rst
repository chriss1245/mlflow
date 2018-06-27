Changelog
=========

0.2.0 (2018-06-27)
------------------

- Added ``mlflow server`` to provide a remote tracking server. This is akin to ``mlflow ui`` with new options:
    - ``--host`` to allow binding to any ports (#27, @mdagost)
    - ``--artifact-repo`` to allow storing artifacts at a remote location, S3 only right now (#78, @mateiz)
    - Server now runs behind gunicorn to allow concurrent requests to be made (#61, @mateiz)
- Tensorflow integration, we now support logging Tensorflow Models directly in the log_artifacts API, Model format, and serving APIs (#28, @juntai-zheng)
- Added ``experiments.list_experiments`` as part of experiments API (#37, @mparkhe)
- Improved support for unicode strings (#79, @smurching)
- Diabetes progression example dataset and training code (#56, @dennyglee)
- Miscellaneous bug and documentation fixes from @Jeffwan, @yupbank, @ndjido, @xueyumusic, @manugarri, @tomasatdatabricks, @stbof, @andyk, @andrewmchen, @jakeret, @0wu, @aarondav

0.1.0 (2018-06-05)
------------------

- Initial version of mlflow.
