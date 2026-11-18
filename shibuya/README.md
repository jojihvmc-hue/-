# 渋谷スクランブル交差点 3Dシーン (Blender)

交差点を中心とした約 640m 四方の範囲を、地図データから自動で作った3Dシーンです。ドローンのように交差点の上を旋回する動画をレンダリングします。

## 使用データ

- **建物の形:** 国土地理院 ベクトルタイル（`experimental_bvmap`、建物レイヤー）
- **地面:** 国土地理院 シームレス空中写真（`seamlessphoto`、ズーム18）

出典: 国土地理院（https://maps.gsi.go.jp/development/ichiran.html）

Google Maps のデータは、利用規約上 3D モデルの作成に取り出せないため使っていません。

## 実物と違うところ

- **建物の高さ:** 地図データに高さがないため、ほとんどの建物は「普通 / 堅ろう / 高層」の区分と面積から推定しています。主要なビル（渋谷スクランブルスクエア、ヒカリエ、マークシティ、109、QFRONT など）だけは、公開されている高さの概略値を使っています。
- **外壁:** 窓のパターンを自動生成したもので、実物のデザインではありません。
- **大型ビジョン・看板・人・車:** 雰囲気を出すために、位置も含めて作ったものです。

## 作り直す手順

```bash
pip install mapbox-vector-tile shapely pillow
python3 prep_data.py              # data/ のタイルから buildings.json と ground.jpg を作る
blender -b -P build_shibuya.py    # shibuya.blend を作る
./render_video.sh                 # frames/ に連番画像を出し、shibuya_scramble.mp4 にする
```

`prep_data.py` は、`data/bv_16_*.pbf`（ベクトルタイル）と `data/photo/18_*.jpg`（空中写真タイル）がダウンロード済みであることを前提にしています。
