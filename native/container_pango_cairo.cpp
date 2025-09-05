#include "container_pango_cairo.h"
#include <cmath>
#include <cstring>

using namespace litehtml;

container_pango_cairo::container_pango_cairo(int viewport_w)
: m_viewport_w(viewport_w) {}

container_pango_cairo::~container_pango_cairo() {
    if (m_cr) { cairo_destroy(m_cr); m_cr = nullptr; }
    m_surface = nullptr; // not owned
}

void container_pango_cairo::attach_surface(cairo_surface_t* surf) {
    if (m_cr) { cairo_destroy(m_cr); m_cr = nullptr; }
    m_surface = surf;
    m_cr = cairo_create(m_surface);
}

Size container_pango_cairo::get_surface_size() const {
    return Size{ cairo_image_surface_get_width(m_surface),
                 cairo_image_surface_get_height(m_surface) };
}

pixel_t container_pango_cairo::pt_to_px(float pt) const {
    // 96 DPI: 1pt = 96/72 px
    return static_cast<pixel_t>(pt * 96.0f / 72.0f);
}

void container_pango_cairo::get_media_features(media_features& media) const {
    media.width         = m_viewport_w;
    media.height        = 0;
    media.device_width  = m_viewport_w;
    media.device_height = 0;
    media.color         = 8;
    media.monochrome    = 0;
    media.color_index   = 256;
    media.resolution    = 96;
}

litehtml::uint_ptr container_pango_cairo::create_font(const font_description& descr,
                                                      const litehtml::document* /*doc*/,
                                                      font_metrics* fm)
{
    auto* fh = new font_handle{
        descr.family.empty() ? std::string("Sans") : descr.family,
        static_cast<int>(std::round(descr.size)),
        descr.weight,
        descr.style == font_style_italic
    };

    PangoLayout* layout = pango_cairo_create_layout(m_cr);
    std::string desc = fh->family + " " + std::to_string(fh->size_px) + "px";
    PangoFontDescription* fd = pango_font_description_from_string(desc.c_str());
    if (fh->italic) pango_font_description_set_style(fd, PANGO_STYLE_ITALIC);
    if (fh->weight >= 600) pango_font_description_set_weight(fd, PANGO_WEIGHT_BOLD);
    pango_layout_set_font_description(layout, fd);
    pango_layout_set_text(layout, "Hg", -1);

    int w=0,h=0;
    pango_layout_get_pixel_size(layout, &w, &h);

    fm->ascent   = std::round(h * 0.8f);
    fm->descent  = h - fm->ascent;
    fm->height   = h;
    fm->x_height = std::round(h * 0.5f);

    g_object_unref(layout);
    pango_font_description_free(fd);

    return (uint_ptr) fh;
}

void container_pango_cairo::delete_font(uint_ptr hFont) {
    delete static_cast<font_handle*>(reinterpret_cast<void*>(hFont));
}

pixel_t container_pango_cairo::text_width(const char* text, uint_ptr hFont) {
    auto* fh = static_cast<font_handle*>(reinterpret_cast<void*>(hFont));
    PangoLayout* layout = pango_cairo_create_layout(m_cr);
    std::string desc = fh->family + " " + std::to_string(fh->size_px) + "px";
    PangoFontDescription* fd = pango_font_description_from_string(desc.c_str());
    if (fh->italic) pango_font_description_set_style(fd, PANGO_STYLE_ITALIC);
    if (fh->weight >= 600) pango_font_description_set_weight(fd, PANGO_WEIGHT_BOLD);
    pango_layout_set_font_description(layout, fd);
    pango_layout_set_text(layout, text ? text : "", -1);
    int w=0,h=0;
    pango_layout_get_pixel_size(layout, &w, &h);
    g_object_unref(layout);
    pango_font_description_free(fd);
    return static_cast<pixel_t>(w);
}

void container_pango_cairo::draw_text(uint_ptr /*hdc*/, const char* text, uint_ptr hFont,
    const web_color color, const position& pos)
{
    auto* fh = static_cast<font_handle*>(reinterpret_cast<void*>(hFont));
    cairo_save(m_cr);
    cairo_set_source_rgba(m_cr, color.red/255.0, color.green/255.0, color.blue/255.0, color.alpha/255.0);
    PangoLayout* layout = pango_cairo_create_layout(m_cr);
    std::string desc = fh->family + " " + std::to_string(fh->size_px) + "px";
    PangoFontDescription* fd = pango_font_description_from_string(desc.c_str());
    if (fh->italic) pango_font_description_set_style(fd, PANGO_STYLE_ITALIC);
    if (fh->weight >= 600) pango_font_description_set_weight(fd, PANGO_WEIGHT_BOLD);
    pango_layout_set_font_description(layout, fd);
    pango_layout_set_width(layout, pos.width * PANGO_SCALE);
    pango_layout_set_text(layout, text ? text : "", -1);
    cairo_move_to(m_cr, pos.x, pos.y);
    pango_cairo_show_layout(m_cr, layout);
    g_object_unref(layout);
    pango_font_description_free(fd);
    cairo_restore(m_cr);
}

static inline void _rgba(cairo_t* cr, const web_color& c) {
    cairo_set_source_rgba(cr, c.red/255.0, c.green/255.0, c.blue/255.0, c.alpha/255.0);
}

void container_pango_cairo::draw_solid_fill(uint_ptr /*hdc*/,
                                            const background_layer& /*layer*/,
                                            const web_color& color)
{
    if(color.alpha == 0) return;
    cairo_save(m_cr);
    _rgba(m_cr, color);
    auto s = get_surface_size();
    cairo_rectangle(m_cr, 0, 0, s.width, s.height);
    cairo_fill(m_cr);
    cairo_restore(m_cr);
}

void container_pango_cairo::draw_borders(uint_ptr, const borders& /*b*/, const position& draw_pos, bool /*root*/)
{
    cairo_save(m_cr);
    cairo_set_line_width(m_cr, 1.0);
    cairo_set_source_rgba(m_cr, 0, 0, 0, 1.0);
    cairo_rectangle(m_cr, draw_pos.x + 0.5, draw_pos.y + 0.5, draw_pos.width - 1.0, draw_pos.height - 1.0);
    cairo_stroke(m_cr);
    cairo_restore(m_cr);
}

void container_pango_cairo::split_text(const char* text,
                                       const std::function<void(const char*)>& on_word,
                                       const std::function<void(const char*)>& on_delim)
{
    // A tiny UTF-8-safe-ish splitter: treat spaces/tabs/newlines as delimiters.
    if (!text) return;
    const char* p = text;
    while (*p) {
        // delimiters
        if (*p==' ' || *p=='\t' || *p=='\n' || *p=='\r') {
            const char buf[2] = {*p, '\0'};
            on_delim(buf);
            ++p;
            continue;
        }
        // word
        const char* start = p;
        while (*p && *p!=' ' && *p!='\t' && *p!='\n' && *p!='\r') ++p;
        std::string w(start, p - start);
        on_word(w.c_str());
    }
}

void container_pango_cairo::draw(document::ptr& doc)
{
    cairo_save(m_cr);
    cairo_set_source_rgba(m_cr, 0.945, 0.945, 0.945, 1.0); // #F1F1F1
    cairo_paint(m_cr);
    cairo_restore(m_cr);

    // New draw: (hdc, x, y, clip)
    doc->draw((uint_ptr)this, 0, 0, nullptr);
}