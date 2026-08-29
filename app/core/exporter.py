"""
导出模块：移植自教程 output_module.py（基于 Landlab 官方 API），日志改为回调。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile

import numpy as np

from .i18n import tr


def export_all(grid, output_dir="results", dem_formats=("ascii", "netcdf"),
               river_min_area=1e5, xllcorner=0.0, yllcorner=0.0, epsg=None,
               field_name="topographic__elevation", log=print):
    """一键导出 DEM + 河网水系（log 参数替代原版 print）。"""
    os.makedirs(output_dir, exist_ok=True)
    log(tr("导出到: {0}").format(output_dir))
    for fmt in dem_formats:
        try:
            if fmt == "ascii":
                export_dem_ascii(grid, os.path.join(output_dir, "dem.asc"), field_name, log)
            elif fmt == "geotiff":
                export_dem_geotiff(grid, os.path.join(output_dir, "dem.tif"), field_name,
                                   xllcorner, yllcorner, epsg, log)
            elif fmt == "netcdf":
                export_dem_netcdf(grid, os.path.join(output_dir, "dem.nc"), log)
            elif fmt == "vtk":
                export_vtk(grid, os.path.join(output_dir, "dem.vtk"), field_name, log)
            elif fmt == "obj":
                export_obj(grid, os.path.join(output_dir, "dem.obj"), field_name, log)
        except Exception as e:
            log(f"  跳过 {fmt}: {e}")
    try:
        nmg = extract_river_network(grid, river_min_area, log)
        if nmg is not None and nmg.number_of_nodes > 0:
            export_river_geojson(nmg, os.path.join(output_dir, "river_network.geojson"), log)
            export_river_shapefile(nmg, os.path.join(output_dir, "river"), epsg, log)
            export_river_csv(nmg, os.path.join(output_dir, "river_nodes.csv"), log)
    except Exception as e:
        log(f"  河网提取跳过: {e}")
    log(tr("导出完成! 文件在: {0}").format(output_dir))


def export_dem_ascii(grid, path, field_name="topographic__elevation", log=print):
    from landlab.io import esri_ascii
    with open(path, "w") as f:
        esri_ascii.dump(grid, f, name=field_name)
    log(f"  DEM (ASCII) -> {path}")


def export_dem_geotiff(grid, path, field_name="topographic__elevation",
                       xllcorner=0.0, yllcorner=0.0, epsg=None, log=print):
    try:
        import rasterio
        from rasterio.transform import from_origin
    except ImportError:
        log("  跳过 GeoTIFF (需 pip install rasterio)")
        return
    ny, nx = grid.shape
    z = grid.at_node[field_name].reshape((ny, nx))
    transform = from_origin(xllcorner, yllcorner + ny * grid.dx, grid.dx, grid.dx)
    with rasterio.open(path, "w", driver="GTiff", height=ny, width=nx,
                       count=1, dtype="float32",
                       crs=f"EPSG:{epsg}" if epsg else None,
                       transform=transform, nodata=-9999.0) as dst:
        dst.write(z.astype(np.float32), 1)
    log(f"  DEM (GeoTIFF) -> {path}")


def export_dem_netcdf(grid, path, log=print):
    from landlab.io.netcdf.write import write_netcdf
    names = [n for n in grid.at_node
             if grid.at_node[n].ndim == 1 and grid.at_node[n].shape[0] == grid.number_of_nodes]
    try:
        write_netcdf(path, grid, names=names)
    except (FileNotFoundError, OSError):
        # netCDF4 库不支持中文路径：先写临时文件再移动（教程实测 workaround）
        tmp = os.path.join(tempfile.gettempdir(), "landlab_tmp.nc")
        write_netcdf(tmp, grid, names=names)
        shutil.move(tmp, path)
    log(f"  DEM (NetCDF) -> {path}, {len(names)} 字段")


def export_vtk(grid, path, field_name="topographic__elevation", log=print):
    from landlab.io import legacy_vtk
    legacy_vtk.write_legacy_vtk(path, grid, z_at_node=field_name,
                                fields=[field_name], clobber=True)
    log(f"  DEM (VTK) -> {path}")


def export_obj(grid, path, field_name="topographic__elevation", log=print):
    from landlab.io import obj
    obj.write_obj(path, grid, field_for_z=field_name, clobber=True)
    log(f"  DEM (OBJ) -> {path}")


def extract_river_network(grid, min_drainage_area=1e5, log=print):
    from landlab.grid.create_network import network_grid_from_raster
    nmg = network_grid_from_raster(grid, minimum_channel_threshold=min_drainage_area)
    log(f"  river: {nmg.number_of_nodes} nodes, {nmg.number_of_links} links "
        f"(A>={min_drainage_area:.0e})")
    return nmg


def export_river_geojson(nmg, path, elev_field="topographic__elevation",
                         area_field="drainage_area", log=print):
    features = []
    for i in range(nmg.number_of_nodes):
        elev = float(nmg.at_node[elev_field][i]) if elev_field in nmg.at_node else 0.0
        area = float(nmg.at_node[area_field][i]) if area_field in nmg.at_node else 0.0
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [float(nmg.x_of_node[i]), float(nmg.y_of_node[i])]},
            "properties": {"id": i, "elevation": elev, "drainage_area": area},
        })
    for i in range(nmg.number_of_links):
        f, t = nmg.nodes_at_link[i]
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [[float(nmg.x_of_node[f]), float(nmg.y_of_node[f])],
                                         [float(nmg.x_of_node[t]), float(nmg.y_of_node[t])]]},
            "properties": {"from": int(f), "to": int(t), "link_id": i},
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, ensure_ascii=False, indent=2)
    log(f"  河网 (GeoJSON) -> {path}")


def export_river_shapefile(nmg, path, epsg=None, log=print):
    try:
        import shapefile
    except ImportError:
        log("  跳过 Shapefile (需 pip install pyshp)")
        return
    base = path
    elev_field = "topographic__elevation" if "topographic__elevation" in nmg.at_node else None
    area_field = "drainage_area" if "drainage_area" in nmg.at_node else None

    w = shapefile.Writer(base + "_nodes.shp", shapeType=shapefile.POINT)
    w.field("id", "N")
    if elev_field:
        w.field("elev", "F", decimal=2)
    if area_field:
        w.field("area", "F", decimal=1)
    for i in range(nmg.number_of_nodes):
        w.point(float(nmg.x_of_node[i]), float(nmg.y_of_node[i]))
        rec = [i]
        if elev_field:
            rec.append(float(nmg.at_node[elev_field][i]))
        if area_field:
            rec.append(float(nmg.at_node[area_field][i]))
        w.record(*rec)
    w.close()

    w = shapefile.Writer(base + "_links.shp", shapeType=shapefile.POLYLINE)
    w.field("from", "N")
    w.field("to", "N")
    w.field("link_id", "N")
    for i in range(nmg.number_of_links):
        f, t = nmg.nodes_at_link[i]
        w.line([[[float(nmg.x_of_node[f]), float(nmg.y_of_node[f])],
                 [float(nmg.x_of_node[t]), float(nmg.y_of_node[t])]]])
        w.record(int(f), int(t), i)
    w.close()

    if epsg:
        prj = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
               'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
               'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
        for s in ["_nodes", "_links"]:
            with open(base + s + ".prj", "w") as f:
                f.write(prj)
    log(f"  河网 (Shapefile) -> {base}_nodes.shp, {base}_links.shp")


def export_river_csv(nmg, path, log=print):
    import csv
    elev_field = "topographic__elevation" if "topographic__elevation" in nmg.at_node else None
    area_field = "drainage_area" if "drainage_area" in nmg.at_node else None
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = ["node_id", "x", "y"]
        if elev_field:
            header.append("elevation")
        if area_field:
            header.append("drainage_area")
        w.writerow(header)
        for i in range(nmg.number_of_nodes):
            row = [i, float(nmg.x_of_node[i]), float(nmg.y_of_node[i])]
            if elev_field:
                row.append(float(nmg.at_node[elev_field][i]))
            if area_field:
                row.append(float(nmg.at_node[area_field][i]))
            w.writerow(row)
    log(f"  河网 (CSV) -> {path}")

    link_path = path.replace(".csv", "_links.csv")
    with open(link_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["link_id", "from_node", "to_node"])
        for i in range(nmg.number_of_links):
            f_, t_ = nmg.nodes_at_link[i]
            w.writerow([i, int(f_), int(t_)])
    log(f"  河段 (CSV) -> {link_path}")
