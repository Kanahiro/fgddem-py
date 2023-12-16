# fgddem-py

基盤地図情報「数値標高モデル」（FG-GML-DEM）をGeoTIFFに変換するCLIツールです。

## usage

```sh
pip install fgddem-py
fgddem input.xml output_dir
fgddem input.zip output_dir # zipファイルも指定可能
fgddem input_dir output_dir # ディレクトリも指定可能
fgddem input_dir output_dir --max_workers 4 # 並列処理数を指定可能
```
