export function approximateLocation(latitude, longitude) {
  return {
    latitude: Math.round(latitude * 100) / 100,
    longitude: Math.round(longitude * 100) / 100,
  };
}

// Single permission-based lookup; never watch or persist a person's location.
export function currentArea(geolocation) {
  return new Promise((resolve, reject) => {
    geolocation.getCurrentPosition(
      ({ coords }) =>
        resolve(approximateLocation(coords.latitude, coords.longitude)),
      reject,
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
    );
  });
}
