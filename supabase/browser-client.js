(function (window) {
  const MODULE_URL = 'https://esm.sh/@supabase/supabase-js@2';
  let clientPromise = null;

  function getConfig() {
    return window.__ABHAZBEREG_SUPABASE_CONFIG__ || null;
  }

  async function getClient() {
    const config = getConfig();
    if (!config || !config.url || !config.anonKey) return null;
    if (!clientPromise) {
      clientPromise = import(MODULE_URL).then(({ createClient }) =>
        createClient(config.url, config.anonKey)
      );
    }
    return clientPromise;
  }

  async function fetchListings(options = {}) {
    const client = await getClient();
    if (!client) return [];

    let query = client
      .from('listings')
      .select('id, slug, source_kind, title, summary, city, page_url, telegram_url, published_at, has_video, cover_url, details, listing_media(*)')
      .eq('is_active', true)
      .order('published_at', { ascending: false, nullsFirst: false });

    if (options.sourceKind) query = query.eq('source_kind', options.sourceKind);
    if (options.slug) query = query.eq('slug', options.slug).limit(1);

    const { data, error } = await query;
    if (error) throw error;
    return data || [];
  }

  async function fetchListingBySlug(slug) {
    const rows = await fetchListings({ slug });
    return rows[0] || null;
  }

  window.ABHAZBEREG_SUPABASE = {
    isConfigured: function () {
      const config = getConfig();
      return Boolean(config && config.url && config.anonKey);
    },
    getClient,
    fetchListings,
    fetchListingBySlug,
  };
})(window);
