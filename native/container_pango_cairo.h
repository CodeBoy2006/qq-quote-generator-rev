#pragma once
#include <litehtml/litehtml.h>
#include <cairo.h>
#include <pango/pangocairo.h>
#include <string>

struct Size { int width{0}; int height{0}; };

class container_pango_cairo : public litehtml::document_container
{
public:
    explicit container_pango_cairo(int viewport_w);
    ~container_pango_cairo();

    // surface lifecycle: created outside; attach here before drawing
    void attach_surface(cairo_surface_t* surf);
    Size get_surface_size() const;

    cairo_surface_t* surface() { return m_surface; }
    cairo_t* cr() { return m_cr; }

    // ---- document_container API (new litehtml) ----
    litehtml::uint_ptr create_font(const char* faceName, int size,
        int weight, litehtml::font_style italic, unsigned int decoration,
        litehtml::font_metrics* fm) override;

    void delete_font(litehtml::uint_ptr hFont) override;

    int text_width(const char* text, litehtml::uint_ptr hFont) override;

    void draw_text(litehtml::uint_ptr hdc, const char* text,
        litehtml::uint_ptr hFont, litehtml::web_color color,
        const litehtml::position& pos) override;

    int pt_to_px(int pt) const override;
    int get_default_font_size() const override { return 16; }
    const char* get_default_font_name() const override { return "Sans"; }

    // Background & borders — current API
    void draw_solid_fill(litehtml::uint_ptr, const litehtml::position& pos,
                         const litehtml::web_color color) override;
    void draw_image(litehtml::uint_ptr, const litehtml::tstring_view& /*url*/,
                    const litehtml::position& /*pos*/, const litehtml::position& /*border_box*/,
                    const litehtml::css_position& /*css_pos*/) override {}
    void draw_linear_gradient(litehtml::uint_ptr, const litehtml::background_layer::linear_gradient&,
                              const litehtml::position&) override {}
    void draw_radial_gradient(litehtml::uint_ptr, const litehtml::background_layer::radial_gradient&,
                              const litehtml::position&) override {}
    void draw_conic_gradient(litehtml::uint_ptr, const litehtml::background_layer::conic_gradient&,
                             const litehtml::position&) override {}

    void draw_borders(litehtml::uint_ptr, const litehtml::borders& borders,
                      const litehtml::position& draw_pos, bool root) override;

    // Misc hooks (no-ops for our headless renderer)
    void set_caption(const char* /*caption*/) override {}
    void set_base_url(const char* base_url) override { m_base_url = base_url ? base_url : ""; }
    void link(litehtml::document*, litehtml::element::ptr /*el*/) override {}
    void on_anchor_click(const char* /*url*/, litehtml::element::ptr /*el*/) override {}
    void set_cursor(const char* /*cursor*/) override {}
    void transform_text(litehtml::string& /*text*/, litehtml::text_transform /*tt*/) override {}
    void import_css(litehtml::string& /*text*/, const litehtml::string& /*url*/,
                    litehtml::string& /*baseurl*/) override {}
    void get_media_features(litehtml::media_features& media) const override;
    const char* get_language() const override { return "en"; }

    litehtml::string resolve_color(const litehtml::string& color) const override { return color; }

    void load_image(const char* /*src*/, const char* /*baseurl*/, bool /*redraw_on_ready*/) override {}
    void get_image_size(const char* /*src*/, const char* /*baseurl*/, litehtml::size& sz) override {
        sz.width = 0; sz.height = 0;
    }
    void draw_list_marker(litehtml::uint_ptr, const litehtml::list_marker& /*marker*/) override {}

    void set_clip(const litehtml::position& /*pos*/, const litehtml::border_radiuses& /*rad*/, bool /*valid_x*/, bool /*valid_y*/) override {}
    void del_clip() override {}

    void get_client_rect(litehtml::position& client) const override {
        client.x = 0; client.y = 0;
        auto s = get_surface_size();
        client.width = s.width; client.height = s.height;
    }

    litehtml::element::ptr create_element(const char* /*tag_name*/,
        const litehtml::string_map& /*attributes*/, litehtml::document* /*doc*/) override {
        return nullptr; // no custom elements
    }

    void draw(litehtml::document::ptr& doc);

private:
    cairo_surface_t* m_surface{nullptr};
    cairo_t* m_cr{nullptr};
    int m_viewport_w{800};
    std::string m_base_url;

    struct font_handle {
        std::string family;
        int size_px;
        int weight;
        bool italic;
    };
};