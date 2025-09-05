#pragma once
#include <litehtml/litehtml.h>
#include <cairo.h>
#include <pango/pangocairo.h>
#include <string>
#include <memory>

struct Size { int width{0}; int height{0}; };

class container_pango_cairo : public litehtml::document_container
{
public:
    explicit container_pango_cairo(int viewport_w);
    ~container_pango_cairo();

    void attach_surface(cairo_surface_t* surf);
    Size get_surface_size() const;

    cairo_surface_t* surface() { return m_surface; }
    cairo_t* cr() { return m_cr; }

    // ====== document_container (newer litehtml) ======
    // Fonts
    litehtml::uint_ptr create_font(const litehtml::font_description& descr,
                                   const litehtml::document* doc,
                                   litehtml::font_metrics* fm) override;
    void delete_font(litehtml::uint_ptr hFont) override;
    litehtml::pixel_t text_width(const char* text, litehtml::uint_ptr hFont) override;

    void draw_text(litehtml::uint_ptr hdc, const char* text,
                   litehtml::uint_ptr hFont, const litehtml::web_color color,
                   const litehtml::position& pos) override;

    litehtml::pixel_t pt_to_px(float pt) const override;
    litehtml::pixel_t get_default_font_size() const override { return 16.0f; }
    const char* get_default_font_name() const override { return "Sans"; }

    // Backgrounds
    void draw_solid_fill(litehtml::uint_ptr hdc,
                         const litehtml::background_layer& layer,
                         const litehtml::web_color& color) override;
    void draw_image(litehtml::uint_ptr /*hdc*/,
                    const litehtml::background_layer& /*layer*/,
                    const std::string& /*url*/,
                    const std::string& /*base_url*/) override {}
    void draw_linear_gradient(litehtml::uint_ptr, const litehtml::background_layer&,
                              const litehtml::background_layer::linear_gradient&) override {}
    void draw_radial_gradient(litehtml::uint_ptr, const litehtml::background_layer&,
                              const litehtml::background_layer::radial_gradient&) override {}
    void draw_conic_gradient(litehtml::uint_ptr, const litehtml::background_layer&,
                             const litehtml::background_layer::conic_gradient&) override {}

    // Borders (kept simple)
    void draw_borders(litehtml::uint_ptr, const litehtml::borders&,
                      const litehtml::position& draw_pos, bool /*root*/) override;

    // Misc glue
    void set_caption(const char* /*caption*/) override {}
    void set_base_url(const char* base_url) override { m_base_url = base_url ? base_url : ""; }
    void link(const std::shared_ptr<litehtml::document>& /*doc*/, const litehtml::element::ptr& /*el*/) override {}
    void on_anchor_click(const char* /*url*/, const litehtml::element::ptr& /*el*/) override {}
    void on_mouse_event(const litehtml::element::ptr& /*el*/, litehtml::mouse_event /*event*/) override {}
    void set_cursor(const char* /*cursor*/) override {}
    void transform_text(litehtml::string& /*text*/, litehtml::text_transform /*tt*/) override {}
    void import_css(litehtml::string& /*text*/, const litehtml::string& /*url*/,
                    litehtml::string& /*baseurl*/) override {}
    void get_media_features(litehtml::media_features& media) const override;
    void get_language(litehtml::string& language, litehtml::string& culture) const override {
        language = "en"; culture.clear();
    }

    litehtml::string resolve_color(const litehtml::string& color) const override { return color; }

    void load_image(const char* /*src*/, const char* /*baseurl*/, bool /*redraw_on_ready*/) override {}
    void get_image_size(const char* /*src*/, const char* /*baseurl*/, litehtml::size& sz) override {
        sz.width = 0; sz.height = 0;
    }
    void draw_list_marker(litehtml::uint_ptr, const litehtml::list_marker& /*marker*/) override {}

    void set_clip(const litehtml::position& /*pos*/, const litehtml::border_radiuses& /*rad*/) override {}
    void del_clip() override {}

    void get_viewport(litehtml::position& viewport) const override {
        viewport.x = 0; viewport.y = 0;
        auto s = get_surface_size();
        viewport.width = s.width; viewport.height = s.height;
    }

    litehtml::element::ptr create_element(const char* /*tag_name*/,
        const litehtml::string_map& /*attributes*/,
        const std::shared_ptr<litehtml::document>& /*doc*/) override {
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