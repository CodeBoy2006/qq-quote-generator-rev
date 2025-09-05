#include <litehtml.h>
#include <cairo.h>
#include <cairo-png.h>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <cstring>
#include <iostream>
#include <nlohmann/json.hpp> // 你也可以换成手写 JSON；这里为清晰起见建议引入（若无则改成手写）

#include "container_pango_cairo.h"

using json = nlohmann::json;
using namespace litehtml;

static std::string read_file(const std::string& path) {
    std::ifstream ifs(path);
    std::stringstream ss; ss << ifs.rdbuf();
    return ss.str();
}

static void write_file(const std::string& path, const std::string& s) {
    std::ofstream ofs(path, std::ios::binary);
    ofs.write(s.data(), s.size());
}

static void write_png(const std::string& path, cairo_surface_t* surface) {
    cairo_status_t st = cairo_surface_write_to_png(surface, path.c_str());
    if (st != CAIRO_STATUS_SUCCESS) {
        std::cerr << "write_to_png failed: " << cairo_status_to_string(st) << std::endl;
        std::exit(1);
    }
}

// 递归遍历 DOM，采集 .placeholder 及 avatar 的元素布局
static void collect_placeholders(litehtml::element::ptr el, std::vector<json>& out, int offset_x=0, int offset_y=0) {
    if(!el) return;
    // 取属性
    auto cls = el->get_attr(_t("class"));
    auto src = el->get_attr(_t("data-src"));
    auto eltid = el->get_attr(_t("data-eltid"));

    // 位置与尺寸
    auto pos = el->get_placement(); // litehtml 里 element::get_placement() 返回 position（相对整页）
    if (cls && std::string(cls).find("placeholder") != std::string::npos) {
        json item;
        item["eltid"] = eltid ? std::string(eltid) : "";
        item["src"]   = src   ? std::string(src) : "";
        item["x"] = pos.x;
        item["y"] = pos.y;
        item["w"] = pos.width;
        item["h"] = pos.height;
        out.push_back(item);
    }

    // avatar 也视作 placeholder（即使没有 class）
    if (eltid && src) {
        // 模板里给 avatar 也放了 data-src/data-eltid
        json item;
        item["eltid"] = std::string(eltid);
        item["src"]   = std::string(src);
        item["x"] = pos.x;
        item["y"] = pos.y;
        item["w"] = pos.width;
        item["h"] = pos.height;
        out.push_back(item);
    }

    for(auto& ch : el->get_children()) {
        collect_placeholders(ch, out, offset_x + pos.x, offset_y + pos.y);
    }
}

int main(int argc, char** argv)
{
    std::string in_html, out_png, out_json;
    int width = 800;

    for(int i=1;i<argc;i++){
        if(std::strcmp(argv[i], "-i")==0 && i+1<argc) in_html = argv[++i];
        else if(std::strcmp(argv[i], "-o")==0 && i+1<argc) out_png = argv[++i];
        else if(std::strcmp(argv[i], "-l")==0 && i+1<argc) out_json = argv[++i];
        else if(std::strcmp(argv[i], "-w")==0 && i+1<argc) width = std::atoi(argv[++i]);
    }
    if(in_html.empty() || out_png.empty() || out_json.empty()){
        std::cerr << "Usage: litehtml_renderer -i in.html -o out.png -l layout.json [-w 800]\n";
        return 1;
    }

    std::string html = read_file(in_html);

    // 创建 litehtml 文档
    container_pango_cairo cont(width);
    auto doc = litehtml::document::createFromString(html.c_str(), &cont, nullptr);

    // 先布局
    doc->render(width);
    auto sz = doc->size();
    int H = std::max(sz.height, 10);

    // 准备 Cairo surface
    cairo_surface_t* surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width + 20, H + 20);
    cont.attach_surface(surface);

    // 绘制
    cont.draw(doc);

    // 输出 PNG
    write_png(out_png, surface);

    // 收集占位元素布局
    std::vector<json> items;
    collect_placeholders(doc->root(), items);

    json layout;
    layout["items"] = items;
    write_file(out_json, layout.dump());

    cairo_destroy(cont.cr());
    cairo_surface_destroy(surface);
    return 0;
}