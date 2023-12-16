import os
import shutil
import argparse
import zipfile
import tempfile
from concurrent import futures

from lxml import etree
import numpy as np
import rasterio


def extract_zip(zip_file: str, output_dir: str) -> (list, str):
    with zipfile.ZipFile(zip_file) as zf:
        zf.extractall(output_dir)
        xml_files = [
            os.path.join(output_dir, f)
            for f in os.listdir(output_dir)
            if f.endswith(".xml")
        ]
    return xml_files


def parse_arg():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_path", type=str, help="input files path: xml, zip, or directory of them"
    )
    parser.add_argument("output_dir", type=str, help="output dir")
    parser.add_argument("--max_workers", type=int, default=1, help="max workers")

    args = parser.parse_args()

    tmpdir = tempfile.mkdtemp(dir=".")  # ZIPファイルを展開したときの一時ディレクトリ、後で消す
    xml_files = []
    if args.input_path.endswith(".zip"):
        # extract xml files on memory
        xml_files = extract_zip(args.input_path, tmpdir)

    elif os.path.isdir(args.input_path):
        # xml or zip
        for f in os.listdir(args.input_path):
            if f.endswith(".xml"):
                xml_files.append(os.path.join(args.input_path, f))
            elif f.endswith(".zip"):
                xml_files += extract_zip(os.path.join(args.input_path, f), tmpdir)
    else:
        xml_files = [args.input_path]

    params = {
        "xml_files": xml_files,
        "output_dir": args.output_dir,
        "max_workers": args.max_workers,
        "temp_dir": tmpdir,
    }
    return params


def process_xml(xml_file: str, output_dir: str):
    print(f"processing {xml_file}")

    parser = etree.XMLParser(huge_tree=True)
    tree = etree.parse(xml_file, parser)
    root = tree.getroot()

    # get metadata
    leftbottom_elem = tree.find("//gml:lowerCorner", namespaces=root.nsmap)
    min_lat, min_lon = list(map(float, leftbottom_elem.text.split(" ")))
    righttop_elem = tree.find("//gml:upperCorner", namespaces=root.nsmap)
    max_lat, max_lon = list(map(float, righttop_elem.text.split(" ")))
    gml_high = tree.find("//gml:high", namespaces=root.nsmap)
    width, height = list(map(lambda v: int(v) + 1, gml_high.text.split(" ")))

    # envelopeで定義されている領域のオフセットが定義されていることがある
    gml_startPoint = tree.find("//gml:startPoint", namespaces=root.nsmap)
    dy, dx = list(map(int, gml_startPoint.text.split(" ")))
    output_width = width - dx
    output_height = height - dy

    # find DEM
    dem = tree.find("//gml:tupleList", namespaces=root.nsmap)
    values = list(map(lambda s: round(float(s.split(",")[1]), 2), dem.text.split()))

    if len(values) != output_width * output_height:
        print(f"invalid fgddem data, skip...: {xml_file}")
        return

    # reshape 1d array to 2d array
    grids = np.array(values).reshape(output_height, output_width)

    # save as tiff
    with rasterio.open(
        os.path.join(output_dir, os.path.basename(xml_file).replace(".xml", ".tif")),
        "w",
        driver="GTiff",
        width=output_width,
        height=output_height,
        count=1,
        nodata=-9999.0,
        dtype=grids.dtype,
        crs="EPSG:6668",
        transform=rasterio.transform.from_bounds(
            min_lon,
            min_lat,
            max_lon,
            max_lat,
            width=output_width,
            height=output_height,
        ),
    ) as dst:
        dst.write(grids, 1)


def main():
    params = parse_arg()
    os.makedirs(params["output_dir"], exist_ok=True)

    with futures.ProcessPoolExecutor(max_workers=params["max_workers"]) as executor:
        for xml_file in params["xml_files"]:
            executor.submit(process_xml, xml_file, params["output_dir"])

    if params["temp_dir"]:
        shutil.rmtree(params["temp_dir"])


if __name__ == "__main__":
    main()
