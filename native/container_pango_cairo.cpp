#include "container_pango_cairo.h"
#include <cstring>
#include <cmath>

using namespace litehtml;

container_pango_cairo::container_pango_cairo(int viewport_w)
: m_viewport_w(viewport_w) {}

container_pango_cairo::~container_pango_cairo() {
    if (m_cr) cairo_destroy(m_cr);
    m_cr = nullptr;
    m_surface = nullptr; // surface 由外部释放
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

int container_pango_cairo::pt_to_px(int pt) const {
    // 96 DPI 下：1pt=96/72 px => 1.3333
    return int(std::round(pt * 96.0 / 72.0));
}

void container_pango_cairo::get_media_features(media_features& media) const {
    media.type = media_type::media_screen;
    media.width = m_viewport_w;
    media.height = 0; // auto
    media.device_width = m_viewport_w;
    media.device_height = 0;
    media.color = 8;
    media.monochrome = 0;
    media.color_index = 256;
    media.resolution = 96;
}

litehtml::uint_ptr container_pango_cairo::create_font(const tchar_t* faceName, int size,
    int weight, font_style italic, unsigned int decoration, font_metrics* fm)
{
    auto* fh = new font_handle{
        std::string(faceName ? faceName : "Sans"),
        pt_to_px(size),
        weight,
        italic == font_style_italic
    };

    // 用 Pango 量度
    PangoLayout* layout = pango_cairo_create_layout(m_cr);
    std::string desc = fh->family + " " + std::to_string(fh->size_px) + "px";
    PangoFontDescription* fd = pango_font_description_from_string(desc.c_str());
    if (fh->italic) pango_font_description_set_style(fd, PANGO_STYLE_ITALIC);
    if (fh->weight >= 600) pango_font_description_set_weight(fd, PANGO_WEIGHT_BOLD);
    pango_layout_set_font_description(layout, fd);
    pango_layout_set_text(layout, "Hg", -1);

    int w=0,h=0;
    pango_layout_get_pixel_size(layout, &w, &h);

    fm->ascent = h * 0.8f;
    fm->descent = h - fm->ascent;
    fm->height = h;
    fm->x_height = h * 0.5f;

    g_object_unref(layout);
    pango_font_description_free(fd);

    return (uint_ptr) fh;
}

void container_pango_cairo::delete_font(uint_ptr hFont) {
    auto* fh = (font_handle*) hFont;
    delete fh;
}

int container_pango_cairo::text_width(const tchar_t* text, uint_ptr hFont) {
    auto* fh = (font_handle*) hFont;
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
    return w;
}

void container_pango_cairo::draw_text(uint_ptr, const tchar_t* text, uint_ptr hFont,
    web_color color, const position& pos)
{
    auto* fh = (font_handle*) hFont;
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

static void _rgba(cairo_t* cr, const litehtml::web_color& c) {
    cairo_set_source_rgba(cr, c.red/255.0, c.green/255.0, c.blue/255.0, c.alpha/255.0);
}

void container_pango_cairo::draw_background(uint_ptr, const background_paint& bg)
{
    // 简化：画纯色背景（忽略背景图）
    if(bg.color.alpha == 0) return;
    cairo_save(m_cr);
    _rgba(m_cr, bg.color);
    cairo_rectangle(m_cr, bg.clip_box.x, bg.clip_box.y, bg.clip_box.width, bg.clip_box.height);
    cairo_fill(m_cr);
    cairo_restore(m_cr);
}

void container_pango_cairo::draw_borders(uint_ptr, const borders& b, const position& draw_pos, bool root)
{
    // 简化：只画实线边框（不处理圆角/花样）
    for(int i=0;i<4;i++) {
        if(b.borders[i].style == border_style_none || b.borders[i].width == 0) continue;
        cairo_save(m_cr);
        _rgba(m_cr, b.borders[i].color);
        cairo_set_line_width(m_cr, b.borders[i].width);
        // 0: left,1: top,2: right,3: bottom
        switch(i) {
            case 0: cairo_move_to(m_cr, draw_pos.x, draw_pos.y);
                    cairo_line_to(m_cr, draw_pos.x, draw_pos.bottom()); break;
            case 1: cairo_move_to(m_cr, draw_pos.x, draw_pos.y);
                    cairo_line_to(m_cr, draw_pos.right(), draw_pos.y); break;
            case 2: cairo_move_to(m_cr, draw_pos.right(), draw_pos.y);
                    cairo_line_to(m_cr, draw_pos.right(), draw_pos.bottom()); break;
            case 3: cairo_move_to(m_cr, draw_pos.x, draw_pos.bottom());
                    cairo_line_to(m_cr, draw_pos.right(), draw_pos.bottom()); break;
        }
        cairo_stroke(m_cr);
        cairo_restore(m_cr);
    }
}

void container_pango_cairo::load_image(const tchar_t* src, const tchar_t* baseurl, bool redraw_on_ready)
{
    // 不加载图片：实现“只画占位”
    (void)src; (void)baseurl; (void)redraw_on_ready;
}

void container_pango_cairo::get_image_size(const tchar_t* src, const tchar_t* baseurl, litehtml::size& sz)
{
    // 不解码图片，返回 0；最终以元素布局尺寸为准
    (void)src; (void)baseurl;
    sz.width = 0; sz.height = 0;
}

void container_pango_cairo::draw(litehtml::document::ptr& doc)
{
    // 背景清屏
    cairo_save(m_cr);
    cairo_set_source_rgba(m_cr, 0.945, 0.945, 0.945, 1.0); // #F1F1F1
    cairo_paint(m_cr);
    cairo_restore(m_cr);

    doc->draw((uint_ptr) this, 0, 0, 0, nullptr);
}