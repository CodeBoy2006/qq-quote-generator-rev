#pragma once
#include <litehtml/litehtml.h>
#include <cairo.h>
#include <pango/pangocairo.h>
#include <string>

struct Size { int width{0}; int height{0}; };

class container_pango_cairo : public litehtml::document_container
{
public:
    container_pango_cairo(int viewport_w);
    ~container_pango_cairo();

    // surface 生命周期由外部管理：先 create_image_surface，再 draw
    void attach_surface(cairo_surface_t* surf);
    Size get_surface_size() const;

    // 供外部将像素写文件
    cairo_surface_t* surface() { return m_surface; }
    cairo_t* cr() { return m_cr; }

    // document_container —— 仅实现必要子集
    litehtml::uint_ptr create_font(const litehtml::tchar_t* faceName, int size,
        int weight, litehtml::font_style italic, unsigned int decoration,
        litehtml::font_metrics* fm) override;

    void delete_font(litehtml::uint_ptr hFont) override;

    int text_width(const litehtml::tchar_t* text, litehtml::uint_ptr hFont) override;

    void draw_text(litehtml::uint_ptr hdc, const litehtml::tchar_t* text,
        litehtml::uint_ptr hFont, litehtml::web_color color,
        const litehtml::position& pos) override;

    int pt_to_px(int pt) const override;
    int get_default_font_size() const override { return 16; }
    const litehtml::tchar_t* get_default_font_name() const override {
        static litehtml::tstring s = litehtml::tstring(_t("Sans"));
        return s.c_str();
    }

    void draw_background(litehtml::uint_ptr, const litehtml::background_paint& bg) override;
    void draw_borders(litehtml::uint_ptr, const litehtml::borders& borders, const litehtml::position& draw_pos, bool root) override;

    void set_caption(const litehtml::tchar_t* caption) override {}
    void set_base_url(const litehtml::tchar_t* base_url) override { m_base_url = litehtml::tstring(base_url); }
    void link(litehtml::document*, litehtml::element::ptr el) override {}
    void on_anchor_click(const litehtml::tchar_t* url, litehtml::element::ptr el) override {}
    void set_cursor(const litehtml::tchar_t* cursor) override {}
    void transform_text(litehtml::tstring& text, litehtml::text_transform tt) override {}
    void import_css(litehtml::tstring& text, const litehtml::tstring& url, litehtml::tstring& baseurl) override {}
    void get_media_features(litehtml::media_features& media) const override;

    litehtml::tstring resolve_color(const litehtml::tstring& color) const override { return color; }

    void load_image(const litehtml::tchar_t* src, const litehtml::tchar_t* baseurl, bool redraw_on_ready) override;
    void get_image_size(const litehtml::tchar_t* src, const litehtml::tchar_t* baseurl, litehtml::size& sz) override;
    void draw_list_marker(litehtml::uint_ptr, const litehtml::list_marker& marker) override {}

    void draw(litehtml::document::ptr& doc);

private:
    cairo_surface_t* m_surface{nullptr};
    cairo_t* m_cr{nullptr};
    int m_viewport_w{800};
    litehtml::tstring m_base_url;

    // 简单的 Pango 字体句柄
    struct font_handle {
        std::string family;
        int size_px;
        int weight;
        bool italic;
    };
};