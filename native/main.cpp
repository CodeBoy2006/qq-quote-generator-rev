#include <litehtml/litehtml.h>
#include <cairo.h>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <cstring>
#include <iostream>
#include <nlohmann/json.hpp>

#include "container_pango_cairo.h"

using json = nlohmann::json;
using namespace litehtml;

static std::string read_file(const std::string& path) {
    std::ifstream ifs(path, std::ios::binary);
    std::stringstream ss; ss << ifs.rdbuf();
    return ss.str();
}

static void write_file(const std::string& path, const std::string& s) {
    std::ofstream ofs(path, std::ios::binary);
    ofs.write(s.data(), s.size());
    ofs.close();
}

static void write_png(const std::string& path, cairo_surface_t* surface) {
    cairo_status_t st = cairo_surface_write_to_png(surface, path.c_str());
    if (st != CAIRO_STATUS_SUCCESS) {
        std::cerr << "write_to_png failed: " << cairo_status_to_string(st) << std::endl;
        std::exit(1);
    }
}

// Recursively visit DOM to collect .placeholder & avatar-like elements
static void collect_placeholders(litehtml::element::ptr el, std::vector<json>& out) {
    if(!el) return;

    const char* cls   = el->get_attr("class", nullptr);
    const char* src   = el->get_attr("data-src", nullptr);
    const char* eltid = el->get_attr("data-eltid", nullptr);

    auto pos = el->get_placement(); // absolute within page

    if (cls && std::string(cls).find("placeholder") != std::string::npos) {
        json item;
        item["eltid"] = eltid ? std::string(eltid) : "";
        item["src"]   = src   ? std::string(src)   : "";
        item["x"] = pos.x;
        item["y"] = pos.y;
        item["w"] = pos.width;
        item["h"] = pos.height;
        out.push_back(item);
    }

    // Treat data-eltid + data-src elements (e.g., avatars) as placeholders too
    if (eltid && src) {
        json item;
        item["eltid"] = std::string(eltid);
        item["src"]   = std::string(src);
        item["x"] = pos.x;
        item["y"] = pos.y;
        item["w"] = pos.width;
        item["h"] = pos.height;
        out.push_back(item);
    }

    for (auto& ch : el->children()) {
        collect_placeholders(ch, out);
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

    // Create litehtml document (UTF-8)
    container_pango_cairo cont(width);
    auto doc = litehtml::document::createFromString(html, &cont);

    // Layout and determine height
    doc->render(width);
    int H = std::max(doc->height(), 10);

    // Prepare Cairo surface with some padding
    cairo_surface_t* surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width + 20, H + 20);
    cont.attach_surface(surface);

    // Draw
    cont.draw(doc);

    // Save PNG
    write_png(out_png, surface);

    // Collect placeholder geometry
    std::vector<json> items;
    collect_placeholders(doc->root(), items);

    json layout;
    layout["items"] = items;
    write_file(out_json, layout.dump());

    // Clean up
    cairo_surface_destroy(surface);
    return 0;
}